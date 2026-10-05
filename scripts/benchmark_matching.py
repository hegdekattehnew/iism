"""How fast is matching at volume, and does it still find the best? (Sprint 49)

Run against the scale harness (`make seed-scale`, then `make benchmark`). It
answers two different questions, and the second is the one that matters:

* **Latency** of the three calls whose cost grows with the catalogue:
  `match_jobs` (a candidate's vacancies), `candidates_for_job` (an employer's
  shortlist) and the scarce-skills reads.
* **Recall**: is the top 20 the function returns the top 20 there *is*? Truth is
  computed here, independently, by scoring **every** vacancy (or candidate)
  that shares a standard through the same `score_match` -- no retrieval cap, no
  retrieval ranking. A system can be fast and confidently wrong: the retrieval
  stage cuts the field *before* the scorer sees it, so a cut that ignores fit
  leaves the scorer ranking an arbitrary 500 and the page looking right.

Two recall figures per side. **Overlap** is the share of the true top 20 that was
returned, by identity, under the production tie-break. **Tie-aware** is the share
of the *returned* top 20 that scores at least as high as the true 20th -- the
same question with ties not counted against a retrieval that picked a different
member of an equal-scoring group. `regret` is the points the best returned result
is short of the best that existed.

It refuses any database whose name does not end in `_scale`.
"""

import argparse
import asyncio
import random
import statistics
import sys
import time
import uuid

from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from api.core.config import get_settings
from api.core.database import dispose_engine, get_sessionmaker
from api.modules.identity import Tenant
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateProfile, Job
from api.modules.matching import match_jobs
from api.modules.matching import service as msvc
from api.modules.matching.employer import (
    _pool_held,
    candidates_for_job,
    market_scarce_skills,
    scarce_skills,
)
from api.modules.matching.scoring import score_match

TOP = 20
CHUNK = 2_000  # bind parameters per IN list: well under asyncpg's 32,767


def _chunks(items: list, n: int = CHUNK):  # type: ignore[type-arg]
    for i in range(0, len(items), n):
        yield items[i : i + n]


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))]


async def _true_top_jobs(db, profile_id):  # type: ignore[no-untyped-def]
    """Every open vacancy sharing a standard, scored. No cap, no proxy."""
    held = await msvc._held_skills(db, profile_id)
    facts = await msvc.candidate_facts(db, profile_id)
    keys = [h.concept_id or h.skill_id for h in held]
    job_ids = list(
        (
            await db.scalars(
                text(
                    "SELECT DISTINCT js.job_id FROM job_skills js "
                    "JOIN skills s ON s.id = js.skill_id JOIN jobs j ON j.id = js.job_id "
                    "WHERE j.status = 'published' AND j.closed_at IS NULL "
                    "AND (s.concept_id = ANY(:k) OR s.id = ANY(:k))"
                ).bindparams(k=keys)
            )
        ).all()
    )
    weights = msvc.weights_from_settings()
    scored = []
    for chunk in _chunks(job_ids):
        requirements = await msvc.requirements_for(db, chunk)
        jobs = {j.id: j for j in (await db.scalars(select(Job).where(Job.id.in_(chunk)))).all()}
        for jid in chunk:
            job, reqs = jobs[jid], requirements.get(jid, [])
            r = score_match(
                reqs,
                held,
                job_level_min=job.nsqf_level_min,
                candidate_level=msvc.attained_level(held, reqs),
                job_min_years=job.experience_min_years,
                candidate_years=facts.years_experience,
                job_embedding=job.embedding,
                candidate_embedding=facts.embedding,
                weights=weights,
            )
            scored.append((job.id, r.score, r.coverage, msvc._locality(job, facts), job.title))
    scored.sort(key=lambda s: (-s[1], -s[2], -s[3], s[4]))
    return scored, len(job_ids)


async def _true_top_candidates(db, job):  # type: ignore[no-untyped-def]
    """Every candidate sharing a standard with the vacancy, scored."""
    reqs = (await msvc.requirements_for(db, [job.id])).get(job.id, [])
    keys = list({r.concept_id or r.skill_id for r in reqs})
    pids = list(
        (
            await db.scalars(
                text(
                    "SELECT DISTINCT cs.profile_id FROM candidate_skills cs "
                    "JOIN skills s ON s.id = cs.skill_id "
                    "WHERE s.concept_id = ANY(:k) OR s.id = ANY(:k)"
                ).bindparams(k=keys)
            )
        ).all()
    )
    weights = msvc.weights_from_settings()
    scored = []
    for chunk in _chunks(pids, 5_000):
        held_by = await _pool_held(db, chunk)
        profiles = {
            p.id: p
            for p in (
                await db.scalars(select(CandidateProfile).where(CandidateProfile.id.in_(chunk)))
            ).all()
        }
        for pid in chunk:
            held = held_by.get(pid, [])
            r = score_match(
                reqs,
                held,
                job_level_min=job.nsqf_level_min,
                candidate_level=msvc.attained_level(held, reqs),
                job_min_years=job.experience_min_years,
                candidate_years=profiles[pid].years_experience,
                job_embedding=job.embedding,
                candidate_embedding=profiles[pid].embedding,
                weights=weights,
            )
            scored.append((pid, r.score, r.coverage))
    scored.sort(key=lambda s: (-s[1], -s[2], str(s[0])))
    return scored, len(pids)


def _recall(returned: list[tuple[uuid.UUID, int]], truth: list[tuple]) -> tuple[int, float, int]:  # type: ignore[type-arg]
    """(overlap out of TOP, tie-aware share, regret in points)."""
    want = {t[0] for t in truth[:TOP]}
    got = [r[0] for r in returned[:TOP]]
    overlap = len(want & set(got))
    floor = truth[min(TOP, len(truth)) - 1][1] if truth else 0
    at_least = sum(1 for r in returned[:TOP] if r[1] >= floor)
    denom = max(1, min(TOP, len(truth)))
    regret = (truth[0][1] - returned[0][1]) if truth and returned else 0
    return overlap, at_least / denom, regret


async def _paths(db, args: argparse.Namespace) -> None:  # type: ignore[no-untyped-def]
    """The rest of the product at volume (Sprint 50): everything but retrieval.

    Each section calls the same service function a request or a cron calls, and tolerates the
    function not existing yet, so the **same file measures `main` and the branch**: the baseline
    is taken from a clean worktree of `main` (see the context file's gotcha on `nohup` and `git`).
    """
    from sqlalchemy import func

    from api.modules.applications.employer_service import inbox
    from api.modules.marketplace.models import CandidateSkill
    from api.modules.notifications import drain
    from api.modules.operations import service as ops

    def ms(since: float) -> float:
        return (time.perf_counter() - since) * 1000

    print("\n== programme report (operator view)")
    t0 = time.perf_counter()
    small = await ops.programme_report(db, "SCALE-PROGRAMME-SMALL")
    took = ms(t0)
    if small.enrolled:
        per = took / small.enrolled
        print(
            f"   {small.enrolled} enrolled: {took:,.0f} ms ({small.matched} matched)   "
            f"{per:,.0f} ms per enrolled candidate; at 10,000 that is {per * 10_000 / 1000:,.0f} s"
        )
    else:
        print("   no SCALE-PROGRAMME-SMALL rows: seed with --enrolled")
    if args.large_programme:
        t0 = time.perf_counter()
        large = await ops.programme_report(db, "SCALE-PROGRAMME")
        print(
            f"   {large.enrolled:,} enrolled: {ms(t0):,.0f} ms ({large.matched:,} matched, "
            f"{large.applied:,} applied)"
        )

    print("\n== employer overview (the heaviest employer)")
    from api.modules.matching import employer as employer_module

    top = (
        await db.execute(
            text(
                "SELECT tenant_id, count(*) n FROM jobs WHERE status = 'published' "
                "AND closed_at IS NULL GROUP BY tenant_id ORDER BY n DESC LIMIT 1"
            )
        )
    ).first()
    if top is not None:
        t0 = time.perf_counter()
        pools = await employer_module.job_pools(db, top[0])
        print(
            f"   job_pools over {len(pools):,} vacancies: {ms(t0):,.0f} ms   "
            f"(sum of pools {sum(p.pool for p in pools):,}, ready {sum(p.ready for p in pools):,})"
        )
    t0 = time.perf_counter()
    total_fn = getattr(employer_module, "candidates_total", None)
    if total_fn is not None:
        total = await total_fn(db)
    else:
        total = await db.scalar(select(func.count(func.distinct(CandidateSkill.profile_id)))) or 0
    print(f"   candidates_total ({total:,}): {ms(t0):,.0f} ms")

    print("\n== notification drain (200 email rows pending behind the in-app backlog)")
    backlog = await db.scalar(text("SELECT count(*) FROM notifications WHERE status = 'pending'"))
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        counts = await drain(db, limit=50)
        times.append(ms(t0))
        print(f"   tick: {times[-1]:,.0f} ms  {counts}")
    print(
        f"   {backlog:,} pending rows at the start; median tick {statistics.median(times):,.0f} ms"
    )

    print("\n== employer inbox (one vacancy, many applicants)")
    job = (await db.scalars(select(Job).where(Job.slug == "scale-job-1"))).first()
    if job is not None:
        t0 = time.perf_counter()
        _job, rows = await inbox(db, job.tenant_id, job.slug)
        print(f"   {len(rows):,} applicants ranked: {ms(t0):,.0f} ms")

    if args.embed:
        print("\n== embedding sweep (profiles; ticks of the worker's cron)")
        from api.modules.matching import tasks as match_tasks

        sql = text(
            "SELECT count(*) FILTER (WHERE embedding IS NOT NULL), "
            "count(*) FILTER (WHERE embedding IS NULL AND EXISTS "
            "  (SELECT 1 FROM candidate_skills s WHERE s.profile_id = candidate_profiles.id)) "
            "FROM candidate_profiles"
        )
        before = (await db.execute(sql)).one()
        for n in range(1, 4):
            t0 = time.perf_counter()
            await match_tasks._refresh_profiles(db)
            now = (await db.execute(sql)).one()
            print(
                f"   tick {n}: {ms(t0):,.0f} ms   embedded {now[0] - before[0]:,} more   "
                f"({now[1]:,} with skills still waiting)"
            )
            before = now

    if args.sweep:
        print("\n== alert sweep (10 vacancies, as the worker's cron runs it)")
        from api.modules.alerts.service import sweep

        t0 = time.perf_counter()
        result = await sweep(db, limit=10)
        print(f"   {ms(t0):,.0f} ms   {result}")


async def main(args: argparse.Namespace) -> None:
    name = make_url(get_settings().database_url).database or ""
    if not name.endswith("_scale"):
        sys.exit(f"Refusing to run against {name!r}: this needs a database ending in '_scale'.")
    rng = random.Random(args.seed)

    async with get_sessionmaker()() as db:
        candidates = int(await db.scalar(text("SELECT count(*) FROM candidate_profiles")) or 0)
        vacancies = int(
            await db.scalar(
                text("SELECT count(*) FROM jobs WHERE status='published' AND closed_at IS NULL")
            )
            or 0
        )
        print(f"database {name}: {candidates:,} candidates, {vacancies:,} open vacancies")
        pids = list(
            (
                await db.scalars(
                    select(CandidateProfile.id)
                    .join(User, User.id == CandidateProfile.user_id)
                    .where(User.phone.like("+9170%"))
                    .order_by(CandidateProfile.id)
                    .limit(20_000)
                )
            ).all()
        )
        jobs = list(
            (
                await db.scalars(
                    select(Job)
                    .where(Job.slug.like("scale-job-%"), Job.status == "published")
                    .order_by(Job.slug)
                    .limit(5_000)
                )
            ).all()
        )
        if not pids or not jobs:
            sys.exit("No synthetic rows: run `make seed-scale` first.")
        cand_sample = rng.sample(pids, min(args.candidates, len(pids)))
        job_sample = rng.sample(jobs, min(args.vacancies, len(jobs)))

        print(f"\n== match_jobs: a candidate's vacancies ({len(cand_sample)} candidates)")
        await match_jobs(db, cand_sample[0], limit=TOP)  # warm the plan cache
        times, results = [], {}
        for pid in cand_sample:
            t0 = time.perf_counter()
            res = await match_jobs(db, pid, limit=TOP)
            times.append((time.perf_counter() - t0) * 1000)
            results[pid] = [(s.job.id, s.result.score) for s in res]
        print(
            f"   latency  p50 {statistics.median(times):.0f} ms   p95 {pct(times, 0.95):.0f} ms   "
            f"max {max(times):.0f} ms"
        )

        print(f"\n== candidates_for_job: an employer's shortlist ({len(job_sample)} vacancies)")
        await candidates_for_job(db, job_sample[0])
        times_e, results_e = [], {}
        for job in job_sample:
            t0 = time.perf_counter()
            res_e = await candidates_for_job(db, job)
            times_e.append((time.perf_counter() - t0) * 1000)
            results_e[job.id] = [(s.profile.id, s.result.score) for s in res_e]
        print(
            f"   latency  p50 {statistics.median(times_e):.0f} ms   "
            f"p95 {pct(times_e, 0.95):.0f} ms   max {max(times_e):.0f} ms"
        )

        print("\n== scarce skills")
        tenant = (
            await db.scalars(select(Tenant).where(Tenant.tenant_type == "employer").limit(1))
        ).first()
        assert tenant is not None
        t0 = time.perf_counter()
        await scarce_skills(db, tenant.id)
        t1 = time.perf_counter()
        await market_scarce_skills(db)
        t2 = time.perf_counter()
        print(f"   one employer {(t1 - t0) * 1000:.0f} ms   whole market {(t2 - t1) * 1000:.0f} ms")

        print("\n== district skill gap (operator view)")
        from api.modules.operations.skill_gap import district_skill_gap, districts_with_demand

        options = await districts_with_demand(db)
        gap_times = []
        shown = None
        for option in options[:8]:
            t0 = time.perf_counter()
            gap = await district_skill_gap(db, option.district_id, limit=15)
            gap_times.append((time.perf_counter() - t0) * 1000)
            shown = shown or gap
        print(
            f"   {len(options)} districts with demand; latency p50 "
            f"{statistics.median(gap_times):.0f} ms   max {max(gap_times):.0f} ms"
        )
        if shown is not None:
            res = "fewer than 5" if shown.residents is None else f"{shown.residents:,}"
            print(
                f"   {shown.district}: {shown.vacancies:,} vacancies, {shown.positions:,} places, "
                f"{res} residents with a declared standard"
            )
            for r in shown.standards[:5]:
                sup = "<5" if r.supply is None else f"{r.supply:,}"
                floor = ">=" if r.shortfall_is_minimum else "  "
                print(
                    f"     {r.name[:46]:46s} demand {r.demand:>5,}  supply {sup:>6}  "
                    f"shortfall {floor}{r.shortfall:,}"
                )

        if not args.no_paths:
            await _paths(db, args)

        if args.no_truth:
            await dispose_engine()
            return

        print(f"\n== recall, candidate side: true top {TOP} vs returned (exhaustive truth)")
        ov, ta, rg, shared = [], [], [], []
        for pid in cand_sample[: args.truth_candidates]:
            truth, n = await _true_top_jobs(db, pid)
            o, t, r = _recall(results[pid], truth)
            ov.append(o), ta.append(t), rg.append(r), shared.append(n)
        print(
            f"   overlap {statistics.mean(ov):.1f}/{TOP}   tie-aware {statistics.mean(ta):.2f}   "
            f"best-missed regret mean {statistics.mean(rg):.1f} max {max(rg)} points   "
            f"({len(ov)} candidates; open vacancies sharing a standard: "
            f"{min(shared):,}-{max(shared):,})"
        )

        print(f"\n== recall, employer side: true top {TOP} vs returned (exhaustive truth)")
        ov, ta, rg, shared = [], [], [], []
        for job in job_sample[: args.truth_vacancies]:
            t0 = time.perf_counter()
            truth_e, n = await _true_top_candidates(db, job)
            o, t, r = _recall(results_e[job.id], truth_e)
            ov.append(o), ta.append(t), rg.append(r), shared.append(n)
            print(f"   ... {job.slug}: {n:,} sharing, truth in {time.perf_counter() - t0:.0f}s")
        print(
            f"   overlap {statistics.mean(ov):.1f}/{TOP}   tie-aware {statistics.mean(ta):.2f}   "
            f"best-missed regret mean {statistics.mean(rg):.1f} max {max(rg)} points   "
            f"({len(ov)} vacancies; candidates sharing a standard: {min(shared):,}-{max(shared):,})"
        )
    await dispose_engine()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=int, default=12, help="candidates to time")
    ap.add_argument("--vacancies", type=int, default=10, help="vacancies to time")
    ap.add_argument("--truth-candidates", type=int, default=12)
    ap.add_argument("--truth-vacancies", type=int, default=5, help="each scores every sharer")
    ap.add_argument("--no-truth", action="store_true", help="latency only")
    ap.add_argument("--no-paths", action="store_true", help="skip the non-retrieval sections")
    ap.add_argument("--large-programme", action="store_true", help="also report 10,000 enrolled")
    ap.add_argument("--embed", action="store_true", help="three embedding-sweep ticks (writes)")
    ap.add_argument("--sweep", action="store_true", help="one alert sweep of 10 vacancies (writes)")
    ap.add_argument("--seed", type=int, default=7)
    asyncio.run(main(ap.parse_args()))
