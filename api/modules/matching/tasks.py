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

from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_sessionmaker

log = structlog.get_logger("iism.matching")

# One sweep's worth. Bounded so a backlog after a bulk import cannot make one
# tick of the worker run for minutes; the next tick picks up where this one
# left off, the same reasoning `RETRIEVAL_LIMIT` uses for scoring.
BATCH_SIZE = 100


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

    jobs = list(
        await db.scalars(
            select(Job).where(Job.status == "published", Job.embedding.is_(None)).limit(BATCH_SIZE)
        )
    )
    if not jobs:
        return 0

    provider = get_embedding_provider()
    for job in jobs:
        skill_ids = list(
            await db.scalars(select(JobSkill.skill_id).where(JobSkill.job_id == job.id))
        )
        text = await embedding_text_for_skills(db, skill_ids)
        if not text:
            # Nothing to embed yet (a job whose standards carry no corpus
            # text at all) -- leave NULL rather than store a meaningless
            # zero vector that would then compare as "similar to nothing".
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

    profiles = list(
        await db.scalars(
            select(CandidateProfile).where(CandidateProfile.embedding.is_(None)).limit(BATCH_SIZE)
        )
    )
    if not profiles:
        return 0

    provider = get_embedding_provider()
    for profile in profiles:
        skill_ids = list(
            await db.scalars(
                select(CandidateSkill.skill_id).where(CandidateSkill.profile_id == profile.id)
            )
        )
        text = await embedding_text_for_skills(db, skill_ids)
        if not text:
            # No declared skills yet -- nothing to embed, and there is
            # nothing for `score_match`'s semantic term to compare either way.
            continue
        profile.embedding = provider.embed(text)
        profile.embedding_provider = provider.name
        profile.embedding_model = provider.model
        profile.embedding_computed_at = func.now()
    await db.commit()
    return len(profiles)
