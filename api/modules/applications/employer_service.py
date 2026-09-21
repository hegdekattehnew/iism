"""The employer's side of an application.

Where the candidate's half is about *choosing* to be seen, this half is about
what an employer may see as a result -- and for how long. Withdrawal is the
boundary: the row stays, so an employer's inbox does not silently rewrite its
own history, and the contact details go.
"""

import uuid
from datetime import datetime
from typing import cast

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import record
from api.modules.applications.models import Application
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, Job
from api.modules.matching import score_profiles
from api.modules.matching.scoring import MatchResult
from api.modules.notifications import enqueue

log = structlog.get_logger("iism.applications")


async def _job_of(db: AsyncSession, tenant_id: uuid.UUID, job_slug: str) -> Job:
    """The vacancy, if it belongs to this organisation.

    Any status: an employer may read the applications to a vacancy they have
    since unpublished. 404 rather than 403 -- a slug that is not theirs tells
    them nothing about whether it exists elsewhere (ADR-038).
    """
    job = await db.scalar(select(Job).where(Job.slug == job_slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


async def inbox(
    db: AsyncSession, tenant_id: uuid.UUID, job_slug: str
) -> tuple[Job, list[tuple[Application, CandidateProfile, User, MatchResult]]]:
    """Everyone who applied to this vacancy, ranked by the same scorer.

    Ranked, not merely listed: an employer reading twenty applications needs
    the same ordering the pool gave them, or the two screens disagree about who
    is the strongest candidate.
    """
    job = await _job_of(db, tenant_id, job_slug)
    rows = (
        await db.execute(
            select(Application, CandidateProfile, User)
            .join(CandidateProfile, CandidateProfile.id == Application.profile_id)
            .join(User, User.id == CandidateProfile.user_id)
            .where(Application.job_id == job.id)
        )
    ).all()
    if not rows:
        return job, []

    # One scoring pass for every applicant, through the shared scorer.
    scores = await score_profiles(db, job, [profile.id for _, profile, _ in rows])
    scored = [
        (application, profile, user, scores[profile.id])
        for application, profile, user in rows
        if profile.id in scores
    ]
    # Score, then application age, then id: stable, and the same ordering the
    # ranked pool uses.
    scored.sort(key=lambda r: (-r[3].score, r[0].created_at, str(r[0].id)))
    return job, scored


async def set_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    job_slug: str,
    application_id: uuid.UUID,
    new_status: str,
) -> Application:
    """Move an application along: shortlisted, rejected, hired."""
    job = await _job_of(db, tenant_id, job_slug)
    application = await db.scalar(
        select(Application).where(Application.id == application_id, Application.job_id == job.id)
    )
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if application.status == "withdrawn":
        # The candidate took it back. Moving it along would put their contact
        # details back on an employer's screen by a side door.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This application has been withdrawn by the candidate"
        )

    application.status = new_status

    # The candidate hears about it. In-app always -- most signed up with a
    # phone and have no email, and SMS waits on DLT registration -- plus email
    # for the minority who do, in whichever language they chose.
    profile = await db.get(CandidateProfile, application.profile_id)
    user = await db.get(User, profile.user_id) if profile is not None else None
    if user is not None:
        payload = {
            "vacancy": job.title,
            "organisation": cast(Tenant, job.tenant).name,
            "status": new_status,
            "path": "/applications",
        }
        for channel in ("in_app", "email"):
            await enqueue(
                db,
                recipient_kind="user",
                recipient_id=user.id,
                channel=channel,
                template="application_status_changed",
                payload=payload,
                locale=user.preferred_locale,
            )
    await db.commit()
    await record(
        db,
        "application_status_changed",
        subject_type="job",
        subject_id=job.id,
        # The status, never who it was about: an employer-side event names no
        # candidate, the same rule the console's own events follow.
        payload={"status": new_status},
    )
    return application


def contact_for(user: User, application: Application) -> dict[str, str | None] | None:
    """The candidate's details, while the application is live."""
    if not application.contact_is_visible:
        return None
    return {"full_name": user.full_name, "phone": user.phone, "email": user.email}


def applied_at(application: Application) -> datetime:
    return application.created_at
