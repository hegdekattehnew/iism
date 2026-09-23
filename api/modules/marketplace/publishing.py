"""Employers writing their own listings.

Until now every job in the database was put there by
`scripts/seed_marketplace.py`, and `marketplace/service.py` imported only
`select`. That script is the specification this module implements: what a
listing must carry, and how its required standards are written.

Three rules it inherits from the seed, each of which prevented a real failure
there and would cause the same one here:

* **`JobSkill` is written by full replacement, not diff.** A partial update that
  leaves a stale link behind is a requirement nobody typed.
* **Duplicate links merge on the strongest signal** — highest importance,
  mandatory beating optional. `uq_job_skill` makes a duplicate a constraint
  violation rather than two requirements, and understating either would weaken
  a requirement the employer actually stated.
* **A job with no required standards is invisible to matching.** The seed fails
  loudly on that; publishing refuses.

And one the seed never had to think about, because it ran alongside the
importer: **geography resolves on write.** `state_id` is what
`match_jobs(state_id=…)` filters on, so a listing without it is findable at
`/jobs` and unfindable by anyone matching on location.
"""

import uuid
from datetime import UTC, datetime
from typing import cast

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.modules.geography import resolve_location
from api.modules.marketplace.listings import (
    load_with_skills,
    resolve_standards,
    unique_slug,
)
from api.modules.marketplace.models import (
    CLOSE_REASONS,
    CandidateProfile,
    Job,
    JobSkill,
)
from api.modules.marketplace.schemas import JobIn, JobSkillIn

log = structlog.get_logger("iism.marketplace")

# Fields copied straight from the payload. Listed rather than `model_dump()`ed
# wholesale so `search_vector` -- GENERATED ALWAYS, and rejected by Postgres on
# any write -- can never reach an INSERT by way of a schema someone extended.
_PLAIN_FIELDS = (
    "title",
    "description",
    "location_state",
    "location_district",
    "employment_type",
    "experience_min_years",
    "experience_max_years",
    "salary_min_inr",
    "salary_max_inr",
    "nsqf_level_min",
)


async def _resolve_skills(
    db: AsyncSession, rows: list[JobSkillIn]
) -> list[tuple[uuid.UUID, int, bool]]:
    """Merged on the strongest signal: highest importance, mandatory beating
    optional. `uq_job_skill` makes a duplicate a constraint violation rather
    than two requirements, and understating either would weaken a requirement
    the employer actually stated.

    Which standards exist, and the refusal of retired ones, is shared with the
    course surface (`listings.resolve_standards`) — that is validation policy,
    and ADR-026 requires both paths to apply the same rules.
    """
    if not rows:
        return []
    ids = await resolve_standards(db, [r.skill_slug for r in rows], verb="required")

    merged: dict[uuid.UUID, tuple[int, bool]] = {}
    for row in rows:
        skill_id = ids[row.skill_slug]
        importance, mandatory = merged.get(skill_id, (0, False))
        merged[skill_id] = (max(importance, row.importance), mandatory or row.is_mandatory)
    return [(sid, imp, mand) for sid, (imp, mand) in merged.items()]


async def _write_skills(db: AsyncSession, job: Job, rows: list[JobSkillIn]) -> None:
    resolved = await _resolve_skills(db, rows)
    await db.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
    for skill_id, importance, is_mandatory in resolved:
        db.add(
            JobSkill(
                job_id=job.id,
                skill_id=skill_id,
                importance=importance,
                is_mandatory=is_mandatory,
            )
        )
    await db.flush()


async def _load(db: AsyncSession, job_id: uuid.UUID) -> Job:
    return cast(Job, await load_with_skills(db, Job, JobSkill, job_id, label="Job"))


async def list_jobs(db: AsyncSession, tenant_id: uuid.UUID) -> list[Job]:
    """This organisation's listings, drafts included."""
    return list(
        (
            await db.scalars(
                select(Job)
                .where(Job.tenant_id == tenant_id)
                .options(
                    selectinload(Job.skills).selectinload(JobSkill.skill),
                    selectinload(Job.tenant),
                )
                .order_by(Job.updated_at.desc())
            )
        ).all()
    )


async def get_job(db: AsyncSession, tenant_id: uuid.UUID, slug: str) -> Job:
    """404, never 403, on someone else's listing — a 403 confirms it exists."""
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return await _load(db, job.id)


async def create_job(db: AsyncSession, tenant_id: uuid.UUID, payload: JobIn) -> Job:
    location = await resolve_location(db, payload.location_state, payload.location_district)
    job = Job(
        slug=await unique_slug(db, Job.slug, payload.title, payload.location_district),
        tenant_id=tenant_id,
        # Explicit. `Job.status` defaults to "published" at the model level, so
        # omitting this would put an unfinished listing straight in front of
        # candidates.
        status="draft",
        state_id=location.state_id,
        district_id=location.district_id,
        **{f: getattr(payload, f) for f in _PLAIN_FIELDS},
    )
    db.add(job)
    await db.flush()
    await _write_skills(db, job, payload.skills)
    await db.commit()
    return await _load(db, job.id)


async def update_job(db: AsyncSession, tenant_id: uuid.UUID, slug: str, payload: JobIn) -> Job:
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    for field in _PLAIN_FIELDS:
        setattr(job, field, getattr(payload, field))
    location = await resolve_location(db, payload.location_state, payload.location_district)
    job.state_id, job.district_id = location.state_id, location.district_id
    # The slug is not regenerated. It is a published URL as soon as the job goes
    # live, and rewriting it on a title tweak breaks every link to it.
    await db.flush()
    await _write_skills(db, job, payload.skills)
    await db.commit()
    return await _load(db, job.id)


async def set_published(db: AsyncSession, tenant_id: uuid.UUID, slug: str, published: bool) -> Job:
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    if published:
        required = await db.scalar(select(JobSkill.id).where(JobSkill.job_id == job.id).limit(1))
        if required is None:
            # Not a nicety. Matching scores concept overlap, so a job requiring
            # nothing can never appear for anyone -- it would be published and
            # permanently unmatchable.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Add at least one required standard before publishing",
            )

    job.status = "published" if published else "draft"
    await db.commit()
    log.info(
        "marketplace.job_published" if published else "marketplace.job_unpublished",
        slug=slug,
    )
    return await _load(db, job.id)


async def close_job(
    db: AsyncSession, tenant_id: uuid.UUID, slug: str, reason: str = "filled"
) -> Job:
    """Stop taking applications, without taking the vacancy down.

    **Closing is not unpublishing.** An unpublished job was never visible; a
    closed one was, people applied to it, and those applications still have to
    be worked through. So a closed vacancy keeps its page, keeps its inbox, and
    simply stops appearing in browse and in anybody's matches.

    Closing an already-closed vacancy is a no-op rather than a 409: the
    employer's intent is already satisfied, and a double-click on "close" is
    not an error worth a red box.
    """
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if reason not in CLOSE_REASONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown reason")
    if job.closed_at is not None:
        return await _load(db, job.id)

    job.closed_at = datetime.now(UTC)
    job.close_reason = reason
    await _tell_live_applicants(db, job)
    await db.commit()
    log.info("marketplace.job_closed", slug=slug, reason=reason)
    return await _load(db, job.id)


async def reopen_job(db: AsyncSession, tenant_id: uuid.UUID, slug: str) -> Job:
    """Take applications again.

    **Clears `closes_at` if it is in the past**, which is not tidiness: leaving
    a stale expiry behind means the worker closes the vacancy again within the
    minute, and the employer sees their own action silently undone.
    """
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    job.closed_at = None
    job.close_reason = None
    if job.closes_at is not None and job.closes_at <= datetime.now(UTC):
        job.closes_at = None
    await db.commit()
    log.info("marketplace.job_reopened", slug=slug)
    return await _load(db, job.id)


async def _tell_live_applicants(db: AsyncSession, job: Job) -> None:
    """Let the people still waiting know the vacancy is closed.

    **Only the ones still in flight** -- `applied` and `shortlisted`. Somebody
    already rejected has been told, and somebody hired does not need to hear
    that the job they got is closed. Withdrawn applicants took themselves out.

    Queued inside the caller's transaction, never sent here (ADR-006): the
    close must not fail because an SMTP server is slow.

    Imported inside the function because `applications` imports this module's
    package for `get_job_by_slug`; at module level this is a cycle, which is
    an ImportError at boot rather than a wrong answer.
    """
    from api.modules.applications.models import Application
    from api.modules.notifications import enqueue

    rows = await db.execute(
        select(Application.profile_id, CandidateProfile.user_id)
        .join(CandidateProfile, CandidateProfile.id == Application.profile_id)
        .where(
            Application.job_id == job.id,
            Application.status.in_(("applied", "shortlisted")),
        )
    )
    for _profile_id, user_id in rows.all():
        await enqueue(
            db,
            recipient_kind="user",
            recipient_id=user_id,
            channel="in_app",
            template="vacancy_closed",
            # The vacancy and a path. Never the reason: "filled" tells an
            # applicant somebody else got it, which is the employer's business
            # to say and not ours to announce on their behalf.
            payload={"vacancy": job.title, "path": "/applications"},
        )


async def delete_job(db: AsyncSession, tenant_id: uuid.UUID, slug: str) -> None:
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    # WARNING, not INFO: irreversible, owner-only, and it is what you go
    # looking for after "our listing disappeared".
    log.warning("marketplace.job_deleted", slug=slug)
    await db.delete(job)
    await db.commit()
