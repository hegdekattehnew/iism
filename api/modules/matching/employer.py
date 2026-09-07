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


@dataclass(frozen=True)
class ScarceSkill:
    """A standard the employer asks for more often than the pool can supply."""

    nos_code: str | None
    name_en: str
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
                Skill.name_en,
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
                name_en=r.name_en,
                proficiency=r.proficiency,
                source=r.source,
            )
        )
    return out


async def _candidates_for(db: AsyncSession, job: Job) -> list[ScoredCandidate]:
    requirements = (await requirements_for(db, [job.id])).get(job.id, [])
    if not requirements:
        return []

    concept_keys = [r.concept_id for r in requirements if r.concept_id]
    skill_keys = [r.skill_id for r in requirements]

    # Retrieval, mirrored: only candidates sharing at least one required
    # standard. Someone with nothing in common scores zero, and a page of zeroes
    # is not a shortlist.
    profile_ids = list(
        (
            await db.scalars(
                select(CandidateSkill.profile_id)
                .join(Skill, Skill.id == CandidateSkill.skill_id)
                .where(Skill.concept_id.in_(concept_keys) | Skill.id.in_(skill_keys))
                .distinct()
                .limit(RETRIEVAL_LIMIT)
            )
        ).all()
    )
    if not profile_ids:
        return []

    held_by_profile = await _pool_held(db, profile_ids)
    profiles = {
        p.id: p
        for p in (
            await db.scalars(select(CandidateProfile).where(CandidateProfile.id.in_(profile_ids)))
        ).all()
    }

    scored = [
        ScoredCandidate(
            profile=profiles[pid],
            result=score_match(
                requirements,
                held_by_profile.get(pid, []),
                job_level_min=job.nsqf_level_min,
                candidate_level=attained_level(held_by_profile.get(pid, []), requirements),
            ),
        )
        for pid in profile_ids
        if pid in profiles
    ]
    # Score, then coverage, then id: a stable order, so the same pool always
    # ranks the same way.
    scored.sort(key=lambda s: (-s.result.score, -s.result.coverage, str(s.profile.id)))
    return scored


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


async def job_pools(db: AsyncSession, tenant_id: uuid.UUID) -> list[JobPool]:
    """Every vacancy this employer has open, with the pool against each."""
    jobs = list(
        (
            await db.scalars(
                select(Job)
                .where(Job.tenant_id == tenant_id, Job.status == "published")
                .order_by(Job.title_en)
            )
        ).all()
    )
    pools: list[JobPool] = []
    for job in jobs:
        scored = await _candidates_for(db, job)
        pools.append(
            JobPool(
                job=job,
                pool=len(scored),
                ready=sum(1 for s in scored if s.result.missing_mandatory == 0),
                nearly=sum(1 for s in scored if s.result.missing_mandatory == 1),
            )
        )
    # Most contested first: the vacancy with the deepest pool is the one an
    # employer can fill today.
    pools.sort(key=lambda p: (-p.ready, -p.pool, p.job.title_en))
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
                Skill.name_en,
                func.count(func.distinct(Job.id)).label("required_by"),
            )
            .join(JobSkill, JobSkill.skill_id == Skill.id)
            .join(Job, Job.id == JobSkill.job_id)
            .where(Job.tenant_id == tenant_id, Job.status == "published")
            .group_by(Skill.id, Skill.concept_id, Skill.nos_code, Skill.name_en)
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
            name_en=r.name_en,
            required_by=r.required_by,
            held_by=(by_concept.get(r.concept_id, 0) if r.concept_id else by_skill.get(r.id, 0)),
        )
        for r in required
    ]
    # Most demanded and least supplied first.
    scarce.sort(key=lambda s: (-s.required_by, s.held_by, s.name_en))
    return scarce[:limit]
