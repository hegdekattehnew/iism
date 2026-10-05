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


def bounded_candidates(job_ids: Sequence[uuid.UUID], weights: ScoreWeights) -> Select[Any]:
    """`(job_id, profile_id, bound)` for every candidate sharing a standard with a vacancy.

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
    bound = retrieval_bound(
        matched.c.earned,
        totals.c.total,
        totals.c.mandatory_total - matched.c.mandatory_held,
        weights,
    )
    return select(matched.c.job_id, matched.c.profile_id, bound.label("bound")).join(
        totals, totals.c.job_id == matched.c.job_id
    )


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
