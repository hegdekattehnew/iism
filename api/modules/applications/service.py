"""Applying, withdrawing and saving.

Two rules carried over from elsewhere in this project, both learned the hard
way:

- **`record()` commits**, so every call here happens *after* the write it
  describes has been committed, never in the middle of one.
- **`ensure_profile` is the single creation path** for a candidate profile and
  commits its own write. Applying is often the first thing a new candidate
  does, so it must work for someone who has never opened `/me/profile`.
"""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import record
from api.modules.applications.models import Application, SavedJob
from api.modules.identity import User
from api.modules.marketplace import ensure_profile, get_job_by_slug
from api.modules.marketplace.models import Job

log = structlog.get_logger("iism.applications")


async def _published_job(db: AsyncSession, job_slug: str) -> Job:
    """The vacancy, if it is one anybody may apply to.

    `get_job_by_slug` is published-only, so a draft or withdrawn vacancy is a
    404 here for the same reason it is a 404 in public browse: applying to a
    listing that is not open is not a thing that can succeed.
    """
    job = await get_job_by_slug(db, job_slug)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


async def apply(
    db: AsyncSession, user: User, *, job_slug: str, message: str | None = None
) -> Application:
    """Apply to a vacancy, sharing contact with that employer for that vacancy.

    Re-applying after a withdrawal reuses the row -- the unique constraint
    means there is only ever one application per candidate per vacancy, and a
    person who changes their mind should not be told they already applied to
    something they took back.
    """
    profile = await ensure_profile(db, user.id)
    job = await _published_job(db, job_slug)

    existing = await db.scalar(
        select(Application).where(
            Application.job_id == job.id, Application.profile_id == profile.id
        )
    )
    now = datetime.now(UTC)
    if existing is not None and existing.status != "withdrawn":
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already applied to this vacancy")

    if existing is not None:
        existing.status = "applied"
        existing.contact_shared_at = now
        existing.contact_revoked_at = None
        if message is not None:
            existing.message = message
        application = existing
    else:
        application = Application(
            job_id=job.id,
            profile_id=profile.id,
            message=message,
            # The consent record: this is the moment the disclosure happens.
            contact_shared_at=now,
        )
        db.add(application)

    await db.commit()
    # After the commit, never inside it: `record()` commits, and a rollback in
    # the middle would take the application with it.
    await record(
        db,
        "application_submitted",
        user_id=user.id,
        subject_type="job",
        subject_id=job.id,
    )
    return await _reload(db, application.id)


async def _reload(db: AsyncSession, application_id: uuid.UUID) -> Application:
    """Re-read with the job (and its organisation) loaded.

    `populate_existing`, because the instance is already in the identity map
    with a stale collection and the query would otherwise return that one --
    the trap `profile_service._load` documents.
    """
    application = await db.scalar(
        select(Application)
        .where(Application.id == application_id)
        .execution_options(populate_existing=True)
    )
    assert application is not None  # noqa: S101 - just written in this session
    return application


async def list_applications(db: AsyncSession, user: User) -> list[Application]:
    profile = await ensure_profile(db, user.id)
    rows = await db.scalars(
        select(Application)
        .where(Application.profile_id == profile.id)
        .order_by(Application.created_at.desc())
    )
    return list(rows.all())


async def withdraw(db: AsyncSession, user: User, application_id: uuid.UUID) -> Application:
    """Take the application back, and the contact details with it."""
    profile = await ensure_profile(db, user.id)
    application = await db.scalar(
        select(Application).where(
            Application.id == application_id, Application.profile_id == profile.id
        )
    )
    # 404 rather than 403: someone else's application is not the caller's
    # business to learn the existence of.
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if application.status == "withdrawn":
        return application

    application.status = "withdrawn"
    application.contact_revoked_at = datetime.now(UTC)
    await db.commit()
    await record(
        db,
        "application_withdrawn",
        user_id=user.id,
        subject_type="job",
        subject_id=application.job_id,
    )
    return await _reload(db, application.id)


async def save_job(db: AsyncSession, user: User, job_slug: str) -> SavedJob:
    """Bookmark a vacancy. Idempotent, and visible to nobody but the caller."""
    profile = await ensure_profile(db, user.id)
    job = await _published_job(db, job_slug)
    existing = await db.scalar(
        select(SavedJob).where(SavedJob.job_id == job.id, SavedJob.profile_id == profile.id)
    )
    if existing is not None:
        return existing

    saved = SavedJob(job_id=job.id, profile_id=profile.id)
    db.add(saved)
    await db.commit()
    await record(db, "job_saved", user_id=user.id, subject_type="job", subject_id=job.id)
    return saved


async def unsave_job(db: AsyncSession, user: User, job_slug: str) -> None:
    """Idempotent: removing a bookmark that is not there is not an error."""
    profile = await ensure_profile(db, user.id)
    job = await get_job_by_slug(db, job_slug)
    if job is None:
        return
    saved = await db.scalar(
        select(SavedJob).where(SavedJob.job_id == job.id, SavedJob.profile_id == profile.id)
    )
    if saved is None:
        return
    await db.delete(saved)
    await db.commit()


async def list_saved(db: AsyncSession, user: User) -> list[SavedJob]:
    profile = await ensure_profile(db, user.id)
    rows = await db.scalars(
        select(SavedJob)
        .where(SavedJob.profile_id == profile.id)
        .order_by(SavedJob.created_at.desc())
    )
    return list(rows.all())
