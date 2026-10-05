"""Semantic-similarity embeddings, computed at write time (Sprint 36, BL-5.1).

One cron, here rather than in `core/tasks.py`: core must not import a feature
module (ADR-014), so it is registered at the composition root in
`api/worker.py` exactly as the analytics purge and the alert sweeps are.

Never inside a request, and never inside `scoring.py` itself (ADR-036) --
"the embedding lives beside the scorer, not inside it" is this story's own
acceptance criterion. A skill write sets the owning row's `embedding` back to
NULL (`marketplace.profile_service._write_skills`, `marketplace.publishing.
_write_skills`); this sweep is the only thing that ever fills it back in,
mirroring the alert sweep's own "claim, then do the work" shape -- cheap when
there is nothing new, one indexed query returning no rows.
"""

import uuid
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_sessionmaker

log = structlog.get_logger("iism.matching")

# One sweep's worth. Bounded so a backlog after a bulk import cannot make one
# tick of the worker run for minutes; the next tick picks up where this one
# left off. 250 rather than 100 (Sprint 50): at 100 every two minutes a 50,000-
# profile backfill took seventeen hours, and a tick of 250 is about a second and
# a half now that the skill ids for the whole batch are read in one query.
BATCH_SIZE = 250


async def refresh_embeddings(ctx: dict[str, Any]) -> dict[str, int]:
    """Never raises: a cron that throws takes the worker's next tick with it,
    and a stale embedding is a ranking quality issue, never a correctness one
    (BL-5.2's own bound -- it can only ever refine a ranking)."""
    try:
        async with get_sessionmaker()() as db:
            jobs = await _refresh_jobs(db)
            profiles = await _refresh_profiles(db)
            return {"jobs": jobs, "profiles": profiles}
    except Exception as error:  # noqa: BLE001 - a cron must not kill the worker
        log.warning("matching.embedding_refresh_failed", error=str(error)[:300])
        return {"jobs": 0, "profiles": 0}


async def _refresh_jobs(db: AsyncSession) -> int:
    from api.adapters.embeddings import get_embedding_provider
    from api.modules.marketplace.models import Job, JobSkill
    from api.modules.skills import embedding_text_for_skills

    provider = get_embedding_provider()
    jobs = list(
        await db.scalars(
            select(Job)
            .where(
                Job.status == "published",
                # Missing, or computed by a different model than the one now
                # configured: vectors from two models are not comparable, and
                # `embedding IS NULL` alone never revisited the old ones.
                Job.embedding.is_(None) | Job.embedding_model.is_distinct_from(provider.model),
            )
            # **Never-looked-at first, then the longest ago** (Sprint 50). Without an order,
            # `LIMIT` returned the same rows every tick, and a row that cannot be embedded stays
            # `embedding IS NULL` for ever -- so once a batch's worth of them existed they held
            # the head of the queue and nothing behind them was ever embedded.
            .order_by(Job.embedding_computed_at.asc().nulls_first(), Job.id)
            .limit(BATCH_SIZE)
        )
    )
    if not jobs:
        return 0

    skills_by_job: dict[uuid.UUID, list[uuid.UUID]] = {}
    for job_id, skill_id in (
        await db.execute(
            select(JobSkill.job_id, JobSkill.skill_id).where(
                JobSkill.job_id.in_([job.id for job in jobs])
            )
        )
    ).all():
        skills_by_job.setdefault(job_id, []).append(skill_id)

    for job in jobs:
        text = await embedding_text_for_skills(db, skills_by_job.get(job.id, []))
        if not text:
            # Nothing to embed yet (a job whose standards carry no corpus
            # text at all) -- leave NULL rather than store a meaningless
            # zero vector that would then compare as "similar to nothing".
            # Stamp that it was looked at, so it goes to the back of the queue
            # instead of being picked again first on the next tick.
            job.embedding_computed_at = func.now()
            continue
        job.embedding = provider.embed(text)
        job.embedding_provider = provider.name
        job.embedding_model = provider.model
        job.embedding_computed_at = func.now()
    await db.commit()
    return len(jobs)


async def _refresh_profiles(db: AsyncSession) -> int:
    from api.adapters.embeddings import get_embedding_provider
    from api.modules.marketplace.models import CandidateProfile, CandidateSkill
    from api.modules.skills import embedding_text_for_skills

    provider = get_embedding_provider()
    profiles = list(
        await db.scalars(
            select(CandidateProfile)
            .where(
                CandidateProfile.embedding.is_(None)
                | CandidateProfile.embedding_model.is_distinct_from(provider.model)
            )
            # See `_refresh_jobs`: a profile with no declared standard cannot be embedded and
            # is common (the profile is created lazily), so without this order a hundred of
            # them stop the sweep for everyone else.
            .order_by(
                CandidateProfile.embedding_computed_at.asc().nulls_first(), CandidateProfile.id
            )
            .limit(BATCH_SIZE)
        )
    )
    if not profiles:
        return 0

    skills_by_profile: dict[uuid.UUID, list[uuid.UUID]] = {}
    for profile_id, skill_id in (
        await db.execute(
            select(CandidateSkill.profile_id, CandidateSkill.skill_id).where(
                CandidateSkill.profile_id.in_([profile.id for profile in profiles])
            )
        )
    ).all():
        skills_by_profile.setdefault(profile_id, []).append(skill_id)

    for profile in profiles:
        text = await embedding_text_for_skills(db, skills_by_profile.get(profile.id, []))
        if not text:
            # No declared skills yet -- nothing to embed, and there is
            # nothing for `score_match`'s semantic term to compare either way.
            profile.embedding_computed_at = func.now()
            continue
        profile.embedding = provider.embed(text)
        profile.embedding_provider = provider.name
        profile.embedding_model = provider.model
        profile.embedding_computed_at = func.now()
    await db.commit()
    return len(profiles)
