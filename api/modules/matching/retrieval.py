"""Which rows reach the scorer: the K best by an upper bound, not an arbitrary K.

Scoring everyone against everything does not survive growth (ADR-007), so each
call retrieves a bounded set and scores only that. The set used to be cut by an
arbitrary key -- `Job.id` for a candidate, the UUID's text for a vacancy -- and
the scorer then ranked what survived. Measured on 50,000 candidates and 5,000
vacancies (Sprint 49, `make benchmark`): of a candidate's true top 20 vacancies,
**2.8 were returned**, and of an employer's, 2.2. The page looked right because
the scorer ordered it correctly; the best matches were never in front of it.

**The bound.** Retrieval now keeps the K highest *upper bounds* on the score.
The score is `coverage` (importance-weighted share of what the job requires that
the person holds) plus three components -- level, experience, evidence -- that
lie in [0, 1] and are not known without loading the candidate, then capped when a
mandatory standard is missing. Treating those three as full marks gives a number
that can only overstate: `bound >= raw` for every pair, where `raw` is the scorer's
unrounded result (the integer score is `round(raw * 100)`, so `score / 100` can sit
up to 0.005 above the bound and no further). The cap is applied to it exactly as the
scorer applies it. So a pair outside the K cannot have a higher unrounded score than
the K-th pair's bound.

**This is retrieval, not a second scorer (ADR-036, ADR-037).** The bound ranks
rows for loading and is never returned, stored, logged or shown; every number a
person sees still comes from `score_match`. What stops the two drifting is not
this docstring but `tests/test_retrieval.py`, which asserts the bound is never
below the score over a randomised marketplace, and that the SQL
agrees with `scoring.py`'s own cap rule.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Float, Select, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from api.core.config import get_settings
from api.modules.marketplace.models import CandidateSkill, Job, JobSkill, open_job
from api.modules.matching.scoring import HeldSkill, ScoreWeights
from api.modules.skills.models import Skill


def retrieval_limit() -> int:
    """K, from configuration, read when called (never bound at import)."""
    return get_settings().match_retrieval_limit


def retrieval_bound(
    earned: ColumnElement[Any],
    total: ColumnElement[Any],
    mandatory_missing: ColumnElement[Any],
    weights: ScoreWeights,
) -> ColumnElement[float]:
    """An upper bound on `score_match`'s unrounded result, as a SQL expression.

    `earned` and `total` are the importance weights (`max(importance, 1)`, as the
    scorer weighs them) of the required standards held and of all of them;
    `mandatory_missing` how many mandatory ones are not held.
    """
    coverage = cast(earned, Float) / cast(total, Float)
    # Level, experience, evidence and semantic similarity are each at most 1.
    headroom = weights.level + weights.experience + weights.evidence_share + weights.semantic
    raw = func.least(1.0, weights.coverage * coverage + headroom)
    # The cap, as `scoring.score_match` applies it: flat at `mandatory_gap_cap`,
    # tapering with coverage below `min_coverage_for_cap`.
    floor = weights.min_coverage_for_cap or 1e-9
    cap = case(
        (mandatory_missing <= 0, 1.0),
        (coverage < floor, weights.mandatory_gap_cap * coverage / floor),
        else_=weights.mandatory_gap_cap,
    )
    return func.least(raw, cap)


def bounded_jobs(
    held: Sequence[HeldSkill],
    *,
    state_id: uuid.UUID | None,
    weights: ScoreWeights,
) -> Select[Any]:
    """`(job_id, bound)` for every open vacancy sharing a standard with `held`.

    Only vacancies sharing at least one required standard appear: one with nothing
    in common cannot score above zero. A separate function from `best_jobs_for` so
    a test can read the bound itself and compare it with the score.
    """
    concept_keys = [h.concept_id for h in held if h.concept_id]
    skill_keys = [h.skill_id for h in held]
    weight = func.greatest(JobSkill.importance, 1)

    matched_q = (
        select(
            JobSkill.job_id.label("job_id"),
            func.sum(weight).label("earned"),
            func.count().filter(JobSkill.is_mandatory).label("mandatory_held"),
        )
        .select_from(JobSkill)
        .join(Job, Job.id == JobSkill.job_id)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(open_job())
        .where(Skill.concept_id.in_(concept_keys) | Skill.id.in_(skill_keys))
        .group_by(JobSkill.job_id)
    )
    if state_id is not None:
        matched_q = matched_q.where(Job.state_id == state_id)
    matched = matched_q.cte("matched")

    totals = (
        select(
            JobSkill.job_id.label("job_id"),
            func.sum(weight).label("total"),
            func.count().filter(JobSkill.is_mandatory).label("mandatory_total"),
        )
        .where(JobSkill.job_id.in_(select(matched.c.job_id)))
        .group_by(JobSkill.job_id)
        .cte("totals")
    )
    bound = retrieval_bound(
        matched.c.earned,
        totals.c.total,
        totals.c.mandatory_total - matched.c.mandatory_held,
        weights,
    )
    return select(matched.c.job_id, bound.label("bound")).join(
        totals, totals.c.job_id == matched.c.job_id
    )


async def best_jobs_for(
    db: AsyncSession,
    held: Sequence[HeldSkill],
    *,
    state_id: uuid.UUID | None,
    limit: int,
    weights: ScoreWeights,
) -> list[uuid.UUID]:
    """The `limit` open vacancies with the highest bound for this candidate.

    Ties on the bound break on the vacancy id, so the same inputs always retrieve
    the same set.
    """
    bounded = bounded_jobs(held, state_id=state_id, weights=weights).subquery("bounded")
    query = select(bounded.c.job_id).order_by(bounded.c.bound.desc(), bounded.c.job_id).limit(limit)
    return list((await db.scalars(query)).all())


def candidate_pair_facts(job_ids: Sequence[uuid.UUID]) -> Select[Any]:
    """`(job_id, profile_id, earned, total, mandatory_missing)` for every candidate sharing a
    standard with a vacancy -- the facts the bound and the overview's counts are both made from.

    Done in the database, per vacancy: the version this replaces loaded every
    `(candidate, standard)` pair that touched any of the vacancies into Python and
    then filtered with `IN (every candidate)` -- 16 seconds for a popular standard,
    and a crash past asyncpg's 32,767 bind parameters.
    """
    req = (
        select(
            JobSkill.id.label("req_id"),
            JobSkill.job_id.label("job_id"),
            func.coalesce(Skill.concept_id, Skill.id).label("key"),
            func.greatest(JobSkill.importance, 1).label("weight"),
            JobSkill.is_mandatory.label("is_mandatory"),
        )
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id.in_(list(job_ids)))
        .cte("req")
    )
    totals = (
        select(
            req.c.job_id,
            func.sum(req.c.weight).label("total"),
            func.count().filter(req.c.is_mandatory).label("mandatory_total"),
        )
        .group_by(req.c.job_id)
        .cte("totals")
    )
    # Which candidates hold each required standard, found by walking *from the
    # requirements* to the skill rows that satisfy them and on to the holders through
    # `candidate_skills.skill_id`'s index. The first version built each candidate's
    # distinct held keys across the whole table, which the planner answered with a
    # scan of every `candidate_skills` row (~350 ms at 890,000). DISTINCT is per
    # requirement row, because the scorer keeps one held row per key: a candidate
    # holding two rows of one concept must count once for that requirement, not twice.
    holder = aliased(Skill)
    pairs = (
        select(
            req.c.req_id,
            req.c.job_id,
            req.c.weight,
            req.c.is_mandatory,
            CandidateSkill.profile_id.label("profile_id"),
        )
        .select_from(req)
        .join(holder, or_(holder.concept_id == req.c.key, holder.id == req.c.key))
        .join(CandidateSkill, CandidateSkill.skill_id == holder.id)
        .distinct()
        .cte("pairs")
    )
    matched = (
        select(
            pairs.c.job_id,
            pairs.c.profile_id,
            func.sum(pairs.c.weight).label("earned"),
            func.count().filter(pairs.c.is_mandatory).label("mandatory_held"),
        )
        .group_by(pairs.c.job_id, pairs.c.profile_id)
        .cte("matched")
    )
    return select(
        matched.c.job_id,
        matched.c.profile_id,
        matched.c.earned,
        totals.c.total,
        (totals.c.mandatory_total - matched.c.mandatory_held).label("mandatory_missing"),
    ).join(totals, totals.c.job_id == matched.c.job_id)


def bounded_candidates(job_ids: Sequence[uuid.UUID], weights: ScoreWeights) -> Select[Any]:
    """`(job_id, profile_id, bound)` for every candidate sharing a standard with a vacancy."""
    facts = candidate_pair_facts(job_ids).subquery("facts")
    bound = retrieval_bound(facts.c.earned, facts.c.total, facts.c.mandatory_missing, weights)
    return select(facts.c.job_id, facts.c.profile_id, bound.label("bound"))


async def pool_counts(
    db: AsyncSession, job_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int, int]]:
    """`(pool, ready, nearly)` per vacancy: every candidate sharing a standard, those missing no
    mandatory standard, and those missing exactly one.

    Counted in the database from the same pair facts the bound uses, with **no scoring and no
    candidate loaded**. `ready` and `nearly` are *defined* by the mandatory-missing count, which
    is exactly what the scorer reports as `missing_mandatory` -- so running `score_match` over
    every sharer to read one integer off each result was a 20-second page for an employer with
    54 vacancies (Sprint 50). And these are the true totals: the pool used to be counted over
    the K candidates retrieved, so a vacancy with more sharers than that undercounted.
    """
    if not job_ids:
        return {}
    facts = candidate_pair_facts(job_ids).subquery("facts")
    rows = (
        await db.execute(
            select(
                facts.c.job_id,
                func.count(),
                func.count().filter(facts.c.mandatory_missing == 0),
                func.count().filter(facts.c.mandatory_missing == 1),
            ).group_by(facts.c.job_id)
        )
    ).all()
    out = dict.fromkeys(job_ids, (0, 0, 0))
    for job_id, pool, ready, nearly in rows:
        out[job_id] = (pool, ready, nearly)
    return out


async def best_candidates_for(
    db: AsyncSession,
    job_ids: Sequence[uuid.UUID],
    *,
    limit: int,
    weights: ScoreWeights,
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """For each vacancy, the `limit` candidates with the highest bound, best first.

    A window per vacancy, so nothing proportional to the pool leaves the database
    but the K rows kept. Ties break on the profile id.
    """
    if not job_ids:
        return {}
    bounded = bounded_candidates(job_ids, weights).subquery("bounded")
    ranked = select(
        bounded.c.job_id,
        bounded.c.profile_id,
        func.row_number()
        .over(
            partition_by=bounded.c.job_id,
            order_by=(bounded.c.bound.desc(), bounded.c.profile_id),
        )
        .label("rank"),
    ).subquery("ranked")
    rows = (
        await db.execute(
            select(ranked.c.job_id, ranked.c.profile_id)
            .where(ranked.c.rank <= limit)
            .order_by(ranked.c.job_id, ranked.c.rank)
        )
    ).all()
    out: dict[uuid.UUID, list[uuid.UUID]] = {job_id: [] for job_id in job_ids}
    for job_id, profile_id in rows:
        out[job_id].append(profile_id)
    return out


def bounded_pairs(
    profile_ids: Sequence[uuid.UUID],
    weights: ScoreWeights,
    *,
    min_bound: float = 0.0,
    prune: bool = True,
) -> Select[Any]:
    """`(profile_id, job_id, bound)` for many candidates at once, open vacancies only.

    With `prune` (the default) and a `min_bound` above the mandatory cap, this takes the
    anchored route below; otherwise the full one. The two return **the same pairs** --
    `tests/test_retrieval.py` holds them to it -- and differ only in how many pairs the
    database has to build to find them.
    """
    if prune and min_bound > weights.mandatory_gap_cap:
        return _bounded_pairs_anchored(profile_ids, weights, min_bound)
    return _bounded_pairs_full(profile_ids, weights, min_bound)


def _bounded_pairs_anchored(
    profile_ids: Sequence[uuid.UUID], weights: ScoreWeights, min_bound: float
) -> Select[Any]:
    """The same pairs, built without enumerating every (candidate, vacancy) that shares a standard.

    Sound only for a `min_bound` above the mandatory cap (the caller checks): a pair with a
    mandatory standard missing is bounded by the cap, so every pair at or above `min_bound`
    holds **all** of its vacancy's mandatory standards -- in particular the one the fewest
    candidates in this batch hold. So a vacancy with a mandatory standard is probed only through
    that anchor (the candidates holding it), and the pairs found are then measured exactly.
    A vacancy with no mandatory standard has no anchor and takes the full route; those are rare
    in practice, and a pair there still has to share a standard to count.

    Measured on 1,000 candidates against 5,148 vacancies: 3.2 million pairs built the full way
    (5.2 s, with the aggregation spilling to disk), 285 thousand this way (0.8 s).
    """
    holder = aliased(Skill)
    required = aliased(Skill)
    held = (
        select(
            CandidateSkill.profile_id.label("profile_id"),
            func.coalesce(holder.concept_id, holder.id).label("key"),
        )
        .join(holder, holder.id == CandidateSkill.skill_id)
        .where(CandidateSkill.profile_id.in_(list(profile_ids)))
        .distinct()
        .cte("held")
    )
    req = (
        select(
            JobSkill.id.label("req_id"),
            JobSkill.job_id.label("job_id"),
            func.coalesce(required.concept_id, required.id).label("key"),
            func.greatest(JobSkill.importance, 1).label("weight"),
            JobSkill.is_mandatory.label("is_mandatory"),
        )
        .select_from(JobSkill)
        .join(required, required.id == JobSkill.skill_id)
        .join(Job, Job.id == JobSkill.job_id)
        .where(open_job())
        .cte("req")
    )
    totals = (
        select(
            req.c.job_id,
            func.sum(req.c.weight).label("total"),
            func.count().filter(req.c.is_mandatory).label("mandatory_total"),
        )
        .group_by(req.c.job_id)
        .cte("totals")
    )
    popularity = select(held.c.key, func.count().label("n")).group_by(held.c.key).cte("popularity")
    # Each vacancy's anchor: its mandatory standard held by the fewest candidates here. Ties on the
    # requirement id, so the choice is deterministic. Any choice would be *correct*; this one is
    # fast. A mandatory standard nobody here holds gives n = 0 and so no candidate pairs at all,
    # which is right: nobody here can be eligible for that vacancy.
    anchor = (
        select(req.c.job_id, req.c.key)
        .select_from(req)
        .outerjoin(popularity, popularity.c.key == req.c.key)
        .where(req.c.is_mandatory)
        .distinct(req.c.job_id)
        .order_by(req.c.job_id, func.coalesce(popularity.c.n, 0), req.c.req_id)
        .cte("anchor")
    )
    probed = (
        select(held.c.profile_id, anchor.c.job_id)
        .select_from(anchor)
        .join(held, held.c.key == anchor.c.key)
        .cte("probed")
    )
    # The anchored pairs joined to their vacancy's requirement rows, **materialised**: left to
    # itself the planner joins every candidate's holdings to every requirement first (4 million
    # rows) and only then to the 285 thousand anchored pairs, which is the whole saving thrown
    # away -- seen in EXPLAIN ANALYZE, not guessed. The fence makes the order the one described.
    probed_req = (
        select(
            probed.c.profile_id,
            probed.c.job_id,
            req.c.key,
            req.c.weight,
            req.c.is_mandatory,
        )
        .select_from(probed)
        .join(req, req.c.job_id == probed.c.job_id)
        .cte("probed_req")
        .prefix_with("MATERIALIZED")
    )
    held_b = held.alias("held_b")
    anchored = (
        select(
            probed_req.c.profile_id,
            probed_req.c.job_id,
            func.sum(probed_req.c.weight).label("earned"),
            func.count().filter(probed_req.c.is_mandatory).label("mandatory_held"),
        )
        .select_from(probed_req)
        .join(
            held_b,
            (held_b.c.profile_id == probed_req.c.profile_id) & (held_b.c.key == probed_req.c.key),
        )
        .group_by(probed_req.c.profile_id, probed_req.c.job_id)
    )
    unanchored = (
        select(
            held.c.profile_id,
            req.c.job_id,
            func.sum(req.c.weight).label("earned"),
            func.count().filter(req.c.is_mandatory).label("mandatory_held"),
        )
        .select_from(held)
        .join(req, req.c.key == held.c.key)
        .join(totals, totals.c.job_id == req.c.job_id)
        .where(totals.c.mandatory_total == 0)
        .group_by(held.c.profile_id, req.c.job_id)
    )
    matched = anchored.union_all(unanchored).cte("matched")
    bound = retrieval_bound(
        matched.c.earned,
        totals.c.total,
        totals.c.mandatory_total - matched.c.mandatory_held,
        weights,
    )
    return (
        select(matched.c.profile_id, matched.c.job_id, bound.label("bound"))
        .join(totals, totals.c.job_id == matched.c.job_id)
        .where(bound >= min_bound)
    )


def _bounded_pairs_full(
    profile_ids: Sequence[uuid.UUID], weights: ScoreWeights, min_bound: float
) -> Select[Any]:
    """Every (candidate, vacancy) pair sharing a standard, bounded, then filtered.

    The batch form of `bounded_jobs`, for a caller that asks one question of a *group* of
    people -- "does this candidate have any serious match" -- and so must not run the
    per-candidate query once per person (`match_jobs` costs ~100 ms; ten thousand
    enrolled candidates is twenty minutes). It walks from the candidates' held standards to
    the requirements that satisfy them and groups by pair.

    No DISTINCT is needed, unlike `bounded_candidates`: `held` is already one row per
    `(profile, key)` and each requirement row appears once, so a join produces each
    `(profile, requirement)` exactly once -- a candidate holding two rows of one concept still
    counts once, because the two collapse in `held`, not afterwards.

    `min_bound` prunes in the database. A pair with a missing mandatory standard is bounded by
    the cap, so a caller asking for a bound above the cap never sees one.
    """
    holder = aliased(Skill)
    required = aliased(Skill)
    held = (
        select(
            CandidateSkill.profile_id.label("profile_id"),
            func.coalesce(holder.concept_id, holder.id).label("key"),
        )
        .join(holder, holder.id == CandidateSkill.skill_id)
        .where(CandidateSkill.profile_id.in_(list(profile_ids)))
        .distinct()
        .cte("held")
    )
    req = (
        select(
            JobSkill.job_id.label("job_id"),
            func.coalesce(required.concept_id, required.id).label("key"),
            func.greatest(JobSkill.importance, 1).label("weight"),
            JobSkill.is_mandatory.label("is_mandatory"),
        )
        .select_from(JobSkill)
        .join(required, required.id == JobSkill.skill_id)
        .join(Job, Job.id == JobSkill.job_id)
        .where(open_job())
        .where(required.concept_id.in_(select(held.c.key)) | required.id.in_(select(held.c.key)))
        .cte("req")
    )
    matched = (
        select(
            held.c.profile_id,
            req.c.job_id,
            func.sum(req.c.weight).label("earned"),
            func.count().filter(req.c.is_mandatory).label("mandatory_held"),
        )
        .select_from(held)
        .join(req, req.c.key == held.c.key)
        .group_by(held.c.profile_id, req.c.job_id)
        .cte("matched")
    )
    weight = func.greatest(JobSkill.importance, 1)
    totals = (
        select(
            JobSkill.job_id.label("job_id"),
            func.sum(weight).label("total"),
            func.count().filter(JobSkill.is_mandatory).label("mandatory_total"),
        )
        .where(JobSkill.job_id.in_(select(matched.c.job_id).distinct()))
        .group_by(JobSkill.job_id)
        .cte("totals")
    )
    bound = retrieval_bound(
        matched.c.earned,
        totals.c.total,
        totals.c.mandatory_total - matched.c.mandatory_held,
        weights,
    )
    return (
        select(matched.c.profile_id, matched.c.job_id, bound.label("bound"))
        .join(totals, totals.c.job_id == matched.c.job_id)
        .where(bound >= min_bound)
    )


async def best_pairs(
    db: AsyncSession,
    profile_ids: Sequence[uuid.UUID],
    *,
    weights: ScoreWeights,
    min_bound: float,
    first: int,
    last: int,
) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
    """Each profile's pairs ranked `first..last` (1-based) by bound, ties on the vacancy id.

    Ranked among the pairs at or above `min_bound` only. That is the same rank
    `best_jobs_for` gives them among *all* of a candidate's pairs, because the pairs above a
    bound are by definition the highest-ranked ones -- so "rank <= K" here means what it means
    there.
    """
    if not profile_ids:
        return []
    bounded = bounded_pairs(profile_ids, weights, min_bound=min_bound).subquery("bounded")
    ranked = select(
        bounded.c.profile_id,
        bounded.c.job_id,
        bounded.c.bound,
        func.row_number()
        .over(
            partition_by=bounded.c.profile_id,
            order_by=(bounded.c.bound.desc(), bounded.c.job_id),
        )
        .label("rank"),
    ).subquery("ranked")
    rows = (
        await db.execute(
            select(ranked.c.profile_id, ranked.c.job_id, ranked.c.bound).where(
                ranked.c.rank >= first, ranked.c.rank <= last
            )
        )
    ).all()
    return [(r.profile_id, r.job_id, float(r.bound)) for r in rows]
