"""Registering interest in a course, and taking it back.

The same two rules `applications/service.py` carries, for the same reasons:

- **`record()` commits**, so every call here happens *after* the write it
  describes has been committed, never in the middle of one.
- **`ensure_profile` is the single creation path** for a candidate profile and
  commits its own write. Registering interest may well be the first thing a
  learner does, so it must work for someone who has never opened `/me/profile`.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.modules.analytics import record
from api.modules.identity import User
from api.modules.identity.models import Tenant
from api.modules.interests.models import CourseInterest
from api.modules.marketplace import ensure_profile, get_course_by_slug
from api.modules.marketplace.models import Course
from api.modules.notifications import enqueue

log = structlog.get_logger("iism.interests")


async def _published_course(db: AsyncSession, course_slug: str) -> Course:
    """The course, if it is one anybody may register for.

    `get_course_by_slug` is published-only, so a draft is a 404 here for the
    same reason it is a 404 in public browse: registering interest in a listing
    that is not open is not a thing that can succeed.
    """
    course = await get_course_by_slug(db, course_slug)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return course


async def register(
    db: AsyncSession, user: User, *, course_slug: str, message: str | None = None
) -> CourseInterest:
    """Tell a provider you want this course, sharing your contact with them.

    Registering again after a withdrawal reuses the row -- the unique
    constraint means there is only ever one interest per learner per course,
    and a person who changes their mind should not be told they already did
    something they took back.
    """
    profile = await ensure_profile(db, user.id)
    course = await _published_course(db, course_slug)
    await _within_daily_cap(db, profile.id)

    existing = await db.scalar(
        select(CourseInterest).where(
            CourseInterest.course_id == course.id, CourseInterest.profile_id == profile.id
        )
    )
    now = datetime.now(UTC)
    if existing is not None and existing.status != "withdrawn":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You have already registered interest in this course"
        )

    if existing is not None:
        existing.status = "registered"
        existing.contact_shared_at = now
        existing.contact_revoked_at = None
        if message is not None:
            existing.message = message
        interest = existing
    else:
        interest = CourseInterest(
            course_id=course.id,
            profile_id=profile.id,
            message=message,
            # The consent record: this is the moment the disclosure happens.
            contact_shared_at=now,
        )
        db.add(interest)

    # Queued in the same transaction as the interest itself: a notification for
    # an interest that did not commit would be a lie, and sending inline would
    # let an SMTP timeout fail the registration (ADR-006).
    await enqueue(
        db,
        recipient_kind="tenant",
        recipient_id=course.tenant_id,
        channel="email",
        template="course_interest_registered",
        # The course and a link, and nothing about the learner: who wants it
        # belongs behind the sign-in, on the interested-learners page.
        payload={
            "course": course.title,
            "path": f"/employer/{cast(Tenant, course.tenant).slug}/courses/{course.slug}/interests",
        },
    )
    await db.commit()
    # After the commit, never inside it: `record()` commits, and a rollback in
    # the middle would take the interest with it.
    await record(
        db,
        "course_interest_registered",
        user_id=user.id,
        subject_type="course",
        subject_id=course.id,
    )
    return await _reload(db, interest.id)


async def _within_daily_cap(db: AsyncSession, profile_id: uuid.UUID) -> None:
    """Refuse a learner who is spraying.

    Counted over the last 24 hours rather than a calendar day, so the limit
    cannot be doubled by waiting for midnight -- and the per-minute write
    limiter does not answer patient spraying at all.
    """
    limit = get_settings().max_course_interests_per_day
    since = datetime.now(UTC) - timedelta(days=1)
    made = await db.scalar(
        select(func.count())
        .select_from(CourseInterest)
        .where(CourseInterest.profile_id == profile_id, CourseInterest.created_at >= since)
    )
    if (made or 0) >= limit:
        log.warning("course_interest.daily_cap_reached", limit=limit)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You have registered interest in a lot of courses today. Try again tomorrow.",
            headers={"retry-after": "3600"},
        )


async def _reload(db: AsyncSession, interest_id: uuid.UUID) -> CourseInterest:
    """Re-read with the course (and its organisation) loaded.

    `populate_existing`, because the instance is already in the identity map
    with a stale collection and the query would otherwise return that one --
    the trap `profile_service._load` documents, and the `MissingGreenlet` 500
    Sprint 21 shipped before it was understood.
    """
    interest = await db.scalar(
        select(CourseInterest)
        .where(CourseInterest.id == interest_id)
        .execution_options(populate_existing=True)
    )
    assert interest is not None  # noqa: S101 - just written in this session
    return interest


async def list_interests(db: AsyncSession, user: User) -> list[CourseInterest]:
    profile = await ensure_profile(db, user.id)
    rows = await db.scalars(
        select(CourseInterest)
        .where(CourseInterest.profile_id == profile.id)
        .order_by(CourseInterest.created_at.desc())
    )
    return list(rows.all())


async def withdraw(db: AsyncSession, user: User, interest_id: uuid.UUID) -> CourseInterest:
    """Take it back, and the contact details with it."""
    profile = await ensure_profile(db, user.id)
    interest = await db.scalar(
        select(CourseInterest).where(
            CourseInterest.id == interest_id, CourseInterest.profile_id == profile.id
        )
    )
    # 404 rather than 403: someone else's interest is not the caller's business
    # to learn the existence of.
    if interest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interest not found")
    if interest.status == "withdrawn":
        return interest

    interest.status = "withdrawn"
    interest.contact_revoked_at = datetime.now(UTC)
    await db.commit()
    await record(
        db,
        "course_interest_withdrawn",
        user_id=user.id,
        subject_type="course",
        subject_id=interest.course_id,
    )
    return await _reload(db, interest.id)
