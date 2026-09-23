"""The same scorer, run the other way round.

`score_match` takes what a job requires and what a person holds. It does not
care which side of that pair the query started from, so ranking candidates for
a vacancy is the candidate-facing engine with its arguments swapped — not a
second scoring implementation. That matters more than the code it saves: two
scorers drift, and the moment they disagree neither number can be defended.

**Nothing here identifies a candidate.** A pool is described by headline,
district, experience and evidence — never by name, phone or email. The employer
surface has no authentication yet (Sprint 4 deferred organisation login because
organisations had nothing to publish, and they still do not), so this endpoint
must be safe to call without one. `mount_employer_console` therefore refuses to
mount in production, the same way the console notification provider refuses to
run there: a demonstration surface that quietly became a live one would be the
worst possible outcome.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.identity.models import Tenant
from api.modules.marketplace.models import CandidateProfile, CandidateSkill, Job, JobSkill
from api.modules.matching.scoring import HeldSkill, MatchResult, score_match
from api.modules.matching.service import RETRIEVAL_LIMIT, attained_level, requirements_for
from api.modules.skills.models import Skill


@dataclass(frozen=True)
class ScoredCandidate:
    profile: CandidateProfile
    result: MatchResult


@dataclass(frozen=True)
class JobPool:
    """One vacancy and the shape of the pool against it."""

    job: Job
    pool: int
    """Candidates sharing at least one required standard."""
    ready: int
    """No mandatory standard missing."""
    nearly: int
    """Missing exactly one mandatory standard — the question an employer asks."""
    applications: int = 0
    """Live applications: applied, shortlisted or hired. Withdrawn ones are not
    a pool an employer can act on, and counting them would overstate it."""
    new_applications: int = 0
    """Still untriaged — the number that means "there is something to do"."""


@dataclass(frozen=True)
class ScarceSkill:
    """A standard the employer asks for more often than the pool can supply."""

    nos_code: str | None
    name: str
    required_by: int
    held_by: int


async def _pool_held(
    db: AsyncSession, profile_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[HeldSkill]]:
    """Held skills for many candidates in one query.

    Per-candidate loading is the obvious shape and the wrong one: it turns a
    twenty-row ranking into twenty round trips, and the cost lands on the page
    an employer looks at first.
    """
    if not profile_ids:
        return {}
    rows = (
        await db.execute(
            select(
                CandidateSkill.profile_id,
                CandidateSkill.skill_id,
                Skill.concept_id,
                Skill.name,
                CandidateSkill.proficiency,
                CandidateSkill.source,
            )
            .join(Skill, Skill.id == CandidateSkill.skill_id)
            .where(CandidateSkill.profile_id.in_(profile_ids))
        )
    ).all()
    out: dict[uuid.UUID, list[HeldSkill]] = {}
    for r in rows:
        out.setdefault(r.profile_id, []).append(
            HeldSkill(
                skill_id=r.skill_id,
                concept_id=r.concept_id,
                name=r.name,
                proficiency=r.proficiency,
                source=r.source,
            )
        )
    return out


async def _candidates_for_jobs(
    db: AsyncSession, jobs: list[Job]
) -> dict[uuid.UUID, list[ScoredCandidate]]:
    """Every job's scored pool, in the same number of queries however many jobs.

    This ran once per job, so the overview an employer opens first grew by
    thirteen statements with every vacancy they posted -- 18 for one, 57 for
    four (Sprint 20). Now: requirements for all jobs, one retrieval over the
    union of their standards, then held skills and profiles for the union of
    candidates. The pools are partitioned in memory and the scorer is unchanged.
    `tests/test_matching.py` counts the statements for one vacancy and for four.
    """
    if not jobs:
        return {}
    requirements = await requirements_for(db, [job.id for job in jobs])
    concept_keys = {r.concept_id for reqs in requirements.values() for r in reqs if r.concept_id}
    skill_keys = {r.skill_id for reqs in requirements.values() for r in reqs}
    if not skill_keys:
        return {job.id: [] for job in jobs}

    # Retrieval, mirrored: only candidates sharing at least one required
    # standard. Someone with nothing in common scores zero, and a page of zeroes
    # is not a shortlist.
    rows = (
        await db.execute(
            select(CandidateSkill.profile_id, Skill.id, Skill.concept_id)
            .join(Skill, Skill.id == CandidateSkill.skill_id)
            .where(Skill.concept_id.in_(concept_keys) | Skill.id.in_(skill_keys))
            .distinct()
        )
    ).all()
    by_concept: dict[uuid.UUID, set[uuid.UUID]] = {}
    by_skill: dict[uuid.UUID, set[uuid.UUID]] = {}
    for profile_id, skill_id, concept_id in rows:
        by_skill.setdefault(skill_id, set()).add(profile_id)
        if concept_id:
            by_concept.setdefault(concept_id, set()).add(profile_id)

    pools: dict[uuid.UUID, list[uuid.UUID]] = {}
    for job in jobs:
        members: set[uuid.UUID] = set()
        for r in requirements.get(job.id, []):
            members |= by_skill.get(r.skill_id, set())
            if r.concept_id:
                members |= by_concept.get(r.concept_id, set())
        # Sorted before the cap, so which candidates survive it is a fact about
        # the data rather than about the order Postgres happened to return rows.
        pools[job.id] = sorted(members, key=str)[:RETRIEVAL_LIMIT]

    everyone = list({pid for pool in pools.values() for pid in pool})
    held_by_profile = await _pool_held(db, everyone)
    profiles = (
        {
            p.id: p
            for p in (
                await db.scalars(select(CandidateProfile).where(CandidateProfile.id.in_(everyone)))
            ).all()
        }
        if everyone
        else {}
    )

    out: dict[uuid.UUID, list[ScoredCandidate]] = {}
    for job in jobs:
        reqs = requirements.get(job.id, [])
        scored = [
            ScoredCandidate(
                profile=profiles[pid],
                result=score_match(
                    reqs,
                    held_by_profile.get(pid, []),
                    job_level_min=job.nsqf_level_min,
                    candidate_level=attained_level(held_by_profile.get(pid, []), reqs),
                    job_min_years=job.experience_min_years,
                    candidate_years=profiles[pid].years_experience,
                ),
            )
            for pid in pools[job.id]
            if pid in profiles and reqs
        ]
        # Score, then coverage, then id: a stable order, so the same pool always
        # ranks the same way.
        scored.sort(key=lambda s: (-s.result.score, -s.result.coverage, str(s.profile.id)))
        out[job.id] = scored
    return out


async def _candidates_for(db: AsyncSession, job: Job) -> list[ScoredCandidate]:
    return (await _candidates_for_jobs(db, [job]))[job.id]


async def candidates_for_job(db: AsyncSession, job: Job) -> list[ScoredCandidate]:
    """The scored pool for one vacancy, ranked best first.

    Exported for the alert sweep (Sprint 27), which needs exactly this and must
    not grow its own idea of "close enough to tell somebody about" -- that
    would be the second scorer ADR-037 forbids, and the first time the two
    disagreed neither number could be defended.

    Still de-identified in the sense that matters: it returns profiles, and
    what reaches an employer is `candidate_card()`. The sweep uses it to decide
    who to write to, and writes to them through the outbox by user id.
    """
    return await _candidates_for(db, job)


async def score_profiles(
    db: AsyncSession, job: Job, profile_ids: list[uuid.UUID]
) -> dict[uuid.UUID, MatchResult]:
    """Score named candidates against one vacancy, whoever they are.

    `_candidates_for_jobs` scores the *retrieved* pool -- people who already
    share a required standard. An applicant need not: anyone may apply, and a
    marketplace that refused the under-qualified would be making the hiring
    decision on the employer's behalf. So this scores exactly the profiles it
    is given, through the same `score_match` (ADR-037). **Do not add a second
    scorer here**; two scorers drift, and the moment they disagree about one
    pair neither number can be defended.
    """
    if not profile_ids:
        return {}
    requirements = (await requirements_for(db, [job.id])).get(job.id, [])
    held_by_profile = await _pool_held(db, profile_ids)
    years: dict[uuid.UUID, int] = {
        row.id: row.years_experience
        for row in (
            await db.execute(
                select(CandidateProfile.id, CandidateProfile.years_experience).where(
                    CandidateProfile.id.in_(profile_ids)
                )
            )
        ).all()
    }
    return {
        pid: score_match(
            requirements,
            held_by_profile.get(pid, []),
            job_level_min=job.nsqf_level_min,
            candidate_level=attained_level(held_by_profile.get(pid, []), requirements),
            job_min_years=job.experience_min_years,
            candidate_years=years.get(pid),
        )
        for pid in profile_ids
    }


async def get_employer(db: AsyncSession, slug: str) -> Tenant | None:
    return await db.scalar(
        select(Tenant).where(Tenant.slug == slug, Tenant.tenant_type == "employer")
    )


async def list_employers(db: AsyncSession) -> list[Tenant]:
    """Employers that actually have a published vacancy.

    An employer with nothing published has no console to show, and offering one
    in a picker leads straight to an empty screen.
    """
    return list(
        (
            await db.scalars(
                select(Tenant)
                .join(Job, Job.tenant_id == Tenant.id)
                .where(Tenant.tenant_type == "employer", Job.status == "published")
                .distinct()
                .order_by(Tenant.name)
            )
        ).all()
    )


async def _application_counts(
    db: AsyncSession, job_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """(live, untriaged) per vacancy, in one query however many vacancies.

    One grouped query, for the same reason the pools are batched: this is the
    page an employer opens first, and a per-job count would put the cost back
    that Sprint 20 took out.
    """
    # Imported inside the function, not at module scope: `applications` imports
    # this module for the scorer, so a module-level import here is a cycle --
    # the same reason `core/authorization.py` imports identity's models inside
    # `_context_for`.
    from api.modules.applications.models import LIVE_STATUSES, Application

    if not job_ids:
        return {}
    rows = (
        await db.execute(
            select(Application.job_id, Application.status, func.count())
            .where(Application.job_id.in_(job_ids))
            .group_by(Application.job_id, Application.status)
        )
    ).all()
    counts: dict[uuid.UUID, tuple[int, int]] = {}
    for job_id, status, total in rows:
        live, new = counts.get(job_id, (0, 0))
        if status in LIVE_STATUSES:
            live += total
        if status == "applied":
            new += total
        counts[job_id] = (live, new)
    return counts


async def job_pools(db: AsyncSession, tenant_id: uuid.UUID) -> list[JobPool]:
    """Every vacancy this employer has open, with the pool against each."""
    jobs = list(
        (
            await db.scalars(
                select(Job)
                .where(Job.tenant_id == tenant_id, Job.status == "published")
                .order_by(Job.title)
            )
        ).all()
    )
    scored_by_job = await _candidates_for_jobs(db, jobs)
    counts = await _application_counts(db, [job.id for job in jobs])
    pools: list[JobPool] = []
    for job in jobs:
        scored = scored_by_job[job.id]
        live, new = counts.get(job.id, (0, 0))
        pools.append(
            JobPool(
                job=job,
                pool=len(scored),
                ready=sum(1 for s in scored if s.result.missing_mandatory == 0),
                nearly=sum(1 for s in scored if s.result.missing_mandatory == 1),
                applications=live,
                new_applications=new,
            )
        )
    # Most contested first: the vacancy with the deepest pool is the one an
    # employer can fill today.
    pools.sort(key=lambda p: (-p.ready, -p.pool, p.job.title))
    return pools


async def rank_candidates(
    db: AsyncSession, tenant_id: uuid.UUID, job_slug: str, *, limit: int = 20
) -> tuple[Job, list[ScoredCandidate]] | None:
    job = await db.scalar(
        select(Job).where(
            Job.slug == job_slug, Job.tenant_id == tenant_id, Job.status == "published"
        )
    )
    if job is None:
        return None
    return job, (await _candidates_for(db, job))[:limit]


async def scarce_skills(
    db: AsyncSession, tenant_id: uuid.UUID, *, limit: int = 8
) -> list[ScarceSkill]:
    """What this employer asks for that the pool cannot supply.

    Counted over the whole candidate base rather than one vacancy's shortlist:
    scarcity is a market fact, and narrowing it to people who already matched
    would make every standard look plentiful.
    """
    required = (
        await db.execute(
            select(
                Skill.id,
                Skill.concept_id,
                Skill.nos_code,
                Skill.name,
                func.count(func.distinct(Job.id)).label("required_by"),
            )
            .join(JobSkill, JobSkill.skill_id == Skill.id)
            .join(Job, Job.id == JobSkill.job_id)
            .where(Job.tenant_id == tenant_id, Job.status == "published")
            .group_by(Skill.id, Skill.concept_id, Skill.nos_code, Skill.name)
        )
    ).all()
    if not required:
        return []

    # Held counts, compared at concept level for the same reason the scorer
    # does: a candidate and an employer who picked different rows for one
    # standard are talking about the same skill.
    held_rows = (
        await db.execute(
            select(
                Skill.id,
                Skill.concept_id,
                func.count(func.distinct(CandidateSkill.profile_id)).label("held_by"),
            )
            .join(CandidateSkill, CandidateSkill.skill_id == Skill.id)
            .group_by(Skill.id, Skill.concept_id)
        )
    ).all()
    by_concept: dict[uuid.UUID, int] = {}
    by_skill: dict[uuid.UUID, int] = {}
    for r in held_rows:
        by_skill[r.id] = r.held_by
        if r.concept_id:
            by_concept[r.concept_id] = by_concept.get(r.concept_id, 0) + r.held_by

    scarce = [
        ScarceSkill(
            nos_code=r.nos_code,
            name=r.name,
            required_by=r.required_by,
            held_by=(by_concept.get(r.concept_id, 0) if r.concept_id else by_skill.get(r.id, 0)),
        )
        for r in required
    ]
    # Most demanded and least supplied first.
    scarce.sort(key=lambda s: (-s.required_by, s.held_by, s.name))
    return scarce[:limit]
