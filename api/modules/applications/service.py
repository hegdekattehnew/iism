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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.modules.analytics import record
from api.modules.applications.models import (
    WAS_HIRED_STATUSES,
    WITHDRAWABLE_STATUSES,
    Application,
    SavedJob,
)
from api.modules.applications.reputation import Reputation, worker_reputation
from api.modules.identity import User
from api.modules.identity.models import Tenant
from api.modules.marketplace import (
    compute_completeness,
    ensure_profile,
    get_job_by_slug,
    get_or_create_profile,
)
from api.modules.marketplace.models import Job
from api.modules.matching import (
    CourseSuggestion,
    MatchResult,
    ScoredJob,
    courses_closing_gap,
    match_jobs,
    score_profiles,
)
from api.modules.notifications import enqueue

# How many of a candidate's best-scoring jobs the dashboard shows (Sprint 40).
# A dashboard tile, not the matches page -- `/me/matches` already lists every
# scored job; this is a preview, so it stays short on purpose.
TOP_MATCHES_LIMIT = 5

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


async def _open_job(db: AsyncSession, job_slug: str) -> Job:
    """The vacancy, if it is still taking applications.

    **409, not 404.** A closed vacancy is not missing -- its page is still
    there, the candidate very likely arrived from it, and telling them it does
    not exist would be a lie they can disprove by pressing Back. Closed is a
    state worth naming, so the interface can say which.
    """
    job = await _published_job(db, job_slug)
    if not job.is_open:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This vacancy is closed and is no longer taking applications"
        )
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
    job = await _open_job(db, job_slug)
    await _within_daily_cap(db, profile.id)

    # Locked, so two requests for the same withdrawn row (a double-tap on a flaky
    # connection) queue instead of both finding it "withdrawn" and both queueing an
    # email to the employer. The *first* application has no row to lock, and there
    # the unique constraint is the arbiter -- see the insert below (Sprint 45).
    existing = await db.scalar(
        select(Application)
        .where(Application.job_id == job.id, Application.profile_id == profile.id)
        .with_for_update(of=Application)
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    if existing is not None and existing.status == "rejected":
        # Not "already applied": that reads as something the candidate can undo, and
        # a rejection is not. The employer's decision stands (Sprint 43, BL-12.6).
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This application was not selected for this vacancy"
        )
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
        try:
            # A savepoint, so losing the race undoes only this insert. Two taps
            # on Apply both find no row; the unique constraint refuses the second,
            # and that is the same answer the second tap would have got a moment
            # later -- "already applied" -- not a 500 (Sprint 45).
            async with db.begin_nested():
                db.add(application)
                await db.flush()
        except IntegrityError:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "You have already applied to this vacancy"
            ) from None

    # Queued in the same transaction as the application itself: a notification
    # for an application that did not commit would be a lie, and sending inline
    # would let an SMTP timeout fail the application (ADR-006).
    await enqueue(
        db,
        recipient_kind="tenant",
        recipient_id=job.tenant_id,
        channel="email",
        template="application_received",
        # The vacancy and a link, and nothing about the candidate: who applied
        # belongs behind the sign-in, on the inbox page.
        payload={
            "vacancy": job.title,
            "path": f"/employer/{cast(Tenant, job.tenant).slug}/jobs/{job.slug}/applications",
        },
    )
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


async def _within_daily_cap(db: AsyncSession, profile_id: uuid.UUID) -> None:
    """Refuse a candidate who is spraying.

    Counted over applications made in the last 24 hours rather than a calendar
    day, so the limit cannot be doubled by waiting for midnight. 429 with
    `retry-after`, like the middleware's own refusals.
    """
    limit = get_settings().max_applications_per_day
    since = datetime.now(UTC) - timedelta(days=1)
    made = await db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.profile_id == profile_id, Application.created_at >= since)
    )
    if (made or 0) >= limit:
        log.warning("application.daily_cap_reached", limit=limit)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You have applied to a lot of vacancies today. Try again tomorrow.",
            headers={"retry-after": "3600"},
        )


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


@dataclass(frozen=True)
class CandidateDashboard:
    """A candidate's landing numbers (Sprint 39, BL-10.1) -- no aggregate of
    any of this exists on `/matches` today, which renders one card per job
    with no summary above it.

    `match_jobs`, never `matches_for`: the latter records `matches_viewed`
    (Sprint 10), and a dashboard tile is not the same act as opening the
    matches page -- the same reason `matches_for` exists as a wrapper at all
    (`match_jobs` is also called by the golden-set harness and the alert
    sweep, neither of which is a candidate looking at anything).
    """

    match_count: int
    best_score: int | None
    applied: int
    shortlisted: int
    hired: int
    profile_completeness: int
    # The `scored` list below, sliced to its best few (Sprint 40) -- zero new
    # queries, since this function already calls `match_jobs` for
    # `match_count`/`best_score`.
    top_matches: list[ScoredJob] = field(default_factory=list)
    rating: Reputation | None = None


async def dashboard(db: AsyncSession, user: User) -> CandidateDashboard:
    profile = await get_or_create_profile(db, user.id)
    # Everything, not the default page: `match_count` is the number of matches,
    # and `len()` of a list cut at twenty can never say more than twenty.
    scored = await match_jobs(db, profile.id, limit=None)

    rows = await db.execute(
        select(Application.status, func.count())
        .where(Application.profile_id == profile.id)
        .group_by(Application.status)
    )
    by_status: dict[str, int] = dict(rows.all())  # type: ignore[arg-type]

    percent, _missing = compute_completeness(profile, user.full_name)
    return CandidateDashboard(
        match_count=len(scored),
        best_score=max((s.result.score for s in scored), default=None),
        applied=by_status.get("applied", 0),
        shortlisted=by_status.get("shortlisted", 0),
        # Everyone ever hired, so a finished gig (`completed`) and a no-show
        # still count; `status == "hired"` alone dropped them once they moved on.
        hired=sum(by_status.get(s, 0) for s in WAS_HIRED_STATUSES),
        profile_completeness=percent,
        top_matches=scored[:TOP_MATCHES_LIMIT],
        rating=await worker_reputation(db, profile.id),
    )


async def withdraw(db: AsyncSession, user: User, application_id: uuid.UUID) -> Application:
    """Take the application back, and the contact details with it."""
    profile = await ensure_profile(db, user.id)
    # `FOR UPDATE`: the status checked below must still be true when the write
    # lands. Without it an employer rejecting at the same instant had their
    # decision overwritten by this withdrawal, or this revocation was overwritten
    # by their status change and left contact visible on a row the candidate had
    # taken back (Sprint 45).
    application = await db.scalar(
        select(Application)
        .where(Application.id == application_id, Application.profile_id == profile.id)
        .with_for_update(of=Application)
        .execution_options(populate_existing=True)
    )
    # 404 rather than 403: someone else's application is not the caller's
    # business to learn the existence of.
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if application.status == "withdrawn":
        return application
    # Only an application nobody has decided on, or one still under consideration,
    # can be taken back. Withdrawing a *rejected* one overwrote the status with no
    # record of what it had been, after which `apply()` reset it to "applied" -- a
    # way to wipe an employer's decision. The outcomes after a hire are history
    # (a completed or no-show gig feeds both sides' reputation) and are not the
    # candidate's to rewrite either (Sprint 43, BL-12.6).
    if application.status not in WITHDRAWABLE_STATUSES:
        detail = (
            "This application was not selected, so it cannot be withdrawn"
            if application.status == "rejected"
            else "A decision has been made on this application, so it cannot be withdrawn here. "
            "Contact the employer."
        )
        raise HTTPException(status.HTTP_409_CONFLICT, detail)

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
    try:
        async with db.begin_nested():
            db.add(saved)
            await db.flush()
    except IntegrityError:
        # Saved twice at once: the other request won, and saving is idempotent, so
        # the right answer is theirs rather than a 500 (Sprint 45).
        won = await db.scalar(
            select(SavedJob)
            .where(SavedJob.job_id == job.id, SavedJob.profile_id == profile.id)
            .execution_options(populate_existing=True)
        )
        assert won is not None  # noqa: S101 - the constraint fired because it exists
        return won
    await db.commit()
    await record(db, "job_saved", user_id=user.id, subject_type="job", subject_id=job.id)
    # Re-read rather than returning the instance just added: a freshly
    # constructed row has no loaded `job`, and touching it in the handler is a
    # lazy load in async context -- MissingGreenlet, a 500. It passed in one
    # test file only because that job happened to be in the identity map
    # already, which is exactly the kind of green that hides a defect.
    reloaded = await db.scalar(
        select(SavedJob).where(SavedJob.id == saved.id).execution_options(populate_existing=True)
    )
    assert reloaded is not None  # noqa: S101 - just committed in this session
    return reloaded


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


@dataclass(frozen=True)
class ApplicationGap:
    """What one of the candidate's own applications was missing, and what would
    close it."""

    application: Application
    result: MatchResult
    courses: list[CourseSuggestion]


async def application_gap(
    db: AsyncSession, user: User, application_id: uuid.UUID
) -> ApplicationGap:
    """The gap behind an application, computed now ("Why not me", Sprint 41).

    **At view time, not at the moment of rejection**, so nothing is recorded and
    nothing can go stale: the job's requirements and the candidate's skills are
    both readable at any moment, and a candidate who has since closed part of
    the gap sees a smaller one, which is what they came to find out. The cost is
    that this is not a frozen record of what the employer saw; an employer who
    edits a vacancy's standards afterwards changes it.

    Runs through `score_profiles`, the same `score_match` every other score
    comes from (ADR-037), and not `match_job_by_slug`, which only answers for an
    open vacancy: the job behind a rejection is very often closed by now.

    404 for an application that is not the caller's, never 403 (ADR-038). The
    employer learns nothing from this: the route is the candidate's own, and a
    job's requirements are already public on its page.
    """
    profile = await ensure_profile(db, user.id)
    application = await db.scalar(
        select(Application).where(
            Application.id == application_id, Application.profile_id == profile.id
        )
    )
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    result = (await score_profiles(db, application.job, [profile.id]))[profile.id]
    courses = await courses_closing_gap(db, result.missing)
    return ApplicationGap(application=application, result=result, courses=courses)
