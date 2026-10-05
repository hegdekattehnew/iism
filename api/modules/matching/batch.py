"""One question asked of many candidates at once (Sprint 50).

`programme_report` needs to know, for every candidate enrolled in a government programme,
whether *any* vacancy is a serious match for them. It used to ask `match_jobs` once per
person inside one request -- about 133 ms each on 5,000 vacancies, so a programme of ten
thousand took twenty-two minutes and, past 32,767, failed on a bind-parameter limit before
the time mattered.

The answer is the same and the work is not. `any(score >= 60 over the candidate's top-K
vacancies)` only needs the pairs that *can* reach 60, and the retrieval bound says which those
are: a pair scoring 60 or more has `bound >= 0.595` (`score - 0.5 <= 100 * bound`, ADR-056), so
the database finds each candidate's pairs at or above that bound, best first, and **only those**
are scored -- exactly, through the one scorer. A candidate is confirmed by the first pair that
scores, and is given up on when its eligible pairs run out. This is a *selection* of which pairs
to score, never a second scorer: every number compared with the threshold is `score_match`'s.

It is equivalent to the loop it replaces, not an approximation of it, and
`tests/test_matching_batch.py` keeps the loop as the oracle.
"""

import uuid
from collections import Counter
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.marketplace.models import CandidateProfile, Job
from api.modules.matching.employer import _pool_held
from api.modules.matching.retrieval import best_pairs, retrieval_limit
from api.modules.matching.scoring import (
    SERIOUS_MATCH_SCORE,
    RequiredSkill,
    ScoreWeights,
    score_match,
)
from api.modules.matching.service import attained_level, requirements_for, weights_from_settings

# Candidates per database round trip. Bounded by the bind-parameter ceiling (an `IN` of
# candidate ids) and by the number of (candidate, vacancy) pairs one aggregation holds.
CHUNK = 2_000
# Pairs scored per candidate per round. Small: a candidate with any serious match is
# usually confirmed by the first few.
ROUND = 10
_IN = 5_000


def _chunks(items: list[uuid.UUID], n: int) -> list[list[uuid.UUID]]:
    return [items[i : i + n] for i in range(0, len(items), n)]


async def _confirm(
    db: AsyncSession,
    pairs: list[tuple[uuid.UUID, uuid.UUID, float]],
    weights: ScoreWeights,
    min_score: int,
) -> set[uuid.UUID]:
    """Score exactly these `(profile, job)` pairs; return the profiles with one at `min_score`+."""
    profile_ids = sorted({p for p, _, _ in pairs})
    job_ids = sorted({j for _, j, _ in pairs})

    requirements: dict[uuid.UUID, list[RequiredSkill]] = {}
    jobs: dict[uuid.UUID, tuple[Decimal | None, int | None, list[float] | None]] = {}
    for chunk in _chunks(job_ids, _IN):
        requirements.update(await requirements_for(db, chunk))
        for row in (
            await db.execute(
                select(Job.id, Job.nsqf_level_min, Job.experience_min_years, Job.embedding).where(
                    Job.id.in_(chunk)
                )
            )
        ).all():
            jobs[row.id] = (row.nsqf_level_min, row.experience_min_years, row.embedding)

    held_by = await _pool_held(db, profile_ids)
    facts: dict[uuid.UUID, tuple[int, list[float] | None]] = {}
    for chunk in _chunks(profile_ids, _IN):
        for fact_row in (
            await db.execute(
                select(
                    CandidateProfile.id,
                    CandidateProfile.years_experience,
                    CandidateProfile.embedding,
                ).where(CandidateProfile.id.in_(chunk))
            )
        ).all():
            facts[fact_row.id] = (fact_row.years_experience, fact_row.embedding)

    confirmed: set[uuid.UUID] = set()
    for profile_id, job_id, _bound in pairs:
        if profile_id in confirmed or job_id not in jobs or profile_id not in facts:
            continue
        level_min, min_years, job_embedding = jobs[job_id]
        reqs = requirements.get(job_id, [])
        held = held_by.get(profile_id, [])
        result = score_match(
            reqs,
            held,
            job_level_min=level_min,
            candidate_level=attained_level(held, reqs),
            job_min_years=min_years,
            candidate_years=facts[profile_id][0],
            job_embedding=job_embedding,
            candidate_embedding=facts[profile_id][1],
            weights=weights,
        )
        if result.score >= min_score:
            confirmed.add(profile_id)
    return confirmed


async def profiles_with_serious_match(
    db: AsyncSession,
    profile_ids: Sequence[uuid.UUID],
    *,
    min_score: int = SERIOUS_MATCH_SCORE,
) -> set[uuid.UUID]:
    """The candidates among `profile_ids` with at least one vacancy scoring `min_score`+.

    "Among their top K vacancies", as `match_jobs` is: the same retrieval limit applies, so this
    agrees with the loop of `match_jobs` calls it replaces, pair for pair.
    """
    weights = weights_from_settings()
    limit = retrieval_limit()
    # score = round(raw * 100) >= min_score  =>  raw >= (min_score - 0.5) / 100, and bound >= raw.
    min_bound = (min_score - 0.5) / 100 - 1e-9

    confirmed: set[uuid.UUID] = set()
    for chunk in _chunks(list(dict.fromkeys(profile_ids)), CHUNK):
        remaining = set(chunk)
        first = 1
        while remaining and first <= limit:
            last = min(first + ROUND - 1, limit)
            pairs = await best_pairs(
                db,
                sorted(remaining),
                weights=weights,
                min_bound=min_bound,
                first=first,
                last=last,
            )
            if not pairs:
                break
            hit = await _confirm(db, pairs, weights, min_score)
            confirmed |= hit
            remaining -= hit
            # A candidate with fewer eligible pairs than the window is wide has none left.
            found = Counter(p for p, _, _ in pairs)
            remaining = {p for p in remaining if found[p] >= last - first + 1}
            first = last + 1
    return confirmed
