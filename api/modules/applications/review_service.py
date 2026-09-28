"""Rating a completed gig engagement, from either side (Sprint 37, Epic B8).

Kept apart from `service.py` (the candidate's own acts) and
`employer_service.py` (the employer's), because a review is reused from both
identity contexts and growing either existing file further would blur that
split -- the same reason `interests/` sits beside `applications/` as a
sibling rather than inside it.
"""

import uuid

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import record
from api.modules.applications.employer_service import _job_of
from api.modules.applications.models import Application, ApplicationReview
from api.modules.identity import User
from api.modules.marketplace import ensure_profile

log = structlog.get_logger("iism.applications")


async def _existing_review(
    db: AsyncSession, application_id: uuid.UUID, subject_role: str
) -> ApplicationReview | None:
    return await db.scalar(
        select(ApplicationReview).where(
            ApplicationReview.application_id == application_id,
            ApplicationReview.subject_role == subject_role,
        )
    )


async def _submit(
    db: AsyncSession,
    application: Application,
    *,
    subject_role: str,
    rating: int,
    comment: str | None,
    author_user_id: uuid.UUID,
) -> ApplicationReview:
    """Reviewable only once the engagement is `completed` (Sprint 37, Epic
    B8). `no_show` is deliberately not reviewable -- it is evidence about the
    cancellation, which the status value already carries, not evidence about
    the work.

    Checked before insert, so a duplicate direction is a friendly 409 rather
    than an `IntegrityError` surfacing as an unhandled 500 -- the same shape
    `apply()`'s own duplicate check already uses for `uq_application_job_profile`.
    """
    if application.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a completed engagement can be reviewed")
    if await _existing_review(db, application.id, subject_role) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This has already been reviewed")

    review = ApplicationReview(
        application_id=application.id,
        subject_role=subject_role,
        rating=rating,
        comment=comment,
        author_user_id=author_user_id,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    # Never the candidate's identity in the payload -- ADR-037's rule applied
    # here as everywhere an analytics payload touches this module.
    await record(
        db,
        "application_review_submitted",
        user_id=author_user_id,
        subject_type="job",
        subject_id=application.job_id,
        payload={"subject_role": subject_role, "rating": rating},
    )
    return review


async def submit_poster_review(
    db: AsyncSession, user: User, application_id: uuid.UUID, *, rating: int, comment: str | None
) -> ApplicationReview:
    """The worker rating the poster. `subject_role="poster"` always -- never a
    value the caller states."""
    profile = await ensure_profile(db, user.id)
    application = await db.scalar(
        select(Application).where(
            Application.id == application_id, Application.profile_id == profile.id
        )
    )
    # 404, not 403: someone else's application is not the caller's business
    # to learn the existence of (ADR-038, `withdraw()`'s own precedent).
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return await _submit(
        db,
        application,
        subject_role="poster",
        rating=rating,
        comment=comment,
        author_user_id=user.id,
    )


async def submit_worker_review(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    job_slug: str,
    application_id: uuid.UUID,
    *,
    rating: int,
    comment: str | None,
    author_user_id: uuid.UUID,
) -> ApplicationReview:
    """The poster rating the worker. `subject_role="worker"` always."""
    job = await _job_of(db, tenant_id, job_slug)
    application = await db.scalar(
        select(Application).where(Application.id == application_id, Application.job_id == job.id)
    )
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return await _submit(
        db,
        application,
        subject_role="worker",
        rating=rating,
        comment=comment,
        author_user_id=author_user_id,
    )
