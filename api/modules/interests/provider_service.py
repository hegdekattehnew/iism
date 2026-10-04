"""The provider's side of an interest.

Where the learner's half is about *choosing* to be seen, this half is about
what a provider may see as a result -- and for how long. Withdrawal is the
boundary: the row stays, so a provider's list does not silently rewrite its own
history, and the contact details go.

**No ranking here, unlike the employer's inbox.** That one sorts by the shared
scorer because a vacancy publishes required standards to score against. A
course publishes what it *teaches*, so there is nothing to rank a learner
against, and inventing something would be the second scorer ADR-037 forbids.
Newest first is the honest order.
"""

import uuid
from dataclasses import dataclass, field
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import record
from api.modules.identity.models import Tenant, User
from api.modules.interests.models import LIVE_STATUSES, CourseInterest
from api.modules.marketplace.models import CandidateProfile, Course
from api.modules.notifications import enqueue


async def _course_of(db: AsyncSession, tenant_id: uuid.UUID, course_slug: str) -> Course:
    """The course, if it belongs to this organisation.

    Any status: a provider may read the interest in a course they have since
    unpublished. 404 rather than 403 -- a slug that is not theirs tells them
    nothing about whether it exists elsewhere (ADR-038).
    """
    course = await db.scalar(
        select(Course).where(Course.slug == course_slug, Course.tenant_id == tenant_id)
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return course


async def interested_learners(
    db: AsyncSession, tenant_id: uuid.UUID, course_slug: str
) -> tuple[Course, list[tuple[CourseInterest, CandidateProfile, User]]]:
    """Everybody who registered interest in this course, newest first."""
    course = await _course_of(db, tenant_id, course_slug)
    rows = (
        await db.execute(
            select(CourseInterest, CandidateProfile, User)
            .join(CandidateProfile, CandidateProfile.id == CourseInterest.profile_id)
            .join(User, User.id == CandidateProfile.user_id)
            .where(CourseInterest.course_id == course.id)
            .order_by(CourseInterest.created_at.desc())
        )
    ).all()
    return course, [(interest, profile, user) for interest, profile, user in rows]


async def counts_by_course(db: AsyncSession, tenant_id: uuid.UUID) -> list[tuple[Course, int, int]]:
    """Interest per course for one provider: `(course, live, total)`.

    The provider's landing surface, and also what puts a count on each card in
    their own course list -- which is why it lives here rather than in
    `marketplace`, which must not read this table (ADR-014).
    """
    rows = (
        await db.execute(
            select(
                Course,
                func.count(CourseInterest.id).filter(CourseInterest.status.in_(LIVE_STATUSES)),
                func.count(CourseInterest.id),
            )
            .outerjoin(CourseInterest, CourseInterest.course_id == Course.id)
            .where(Course.tenant_id == tenant_id)
            .group_by(Course.id)
            .order_by(func.count(CourseInterest.id).desc(), Course.title)
        )
    ).all()
    return [(course, int(live or 0), int(total or 0)) for course, live, total in rows]


async def enrolment_conversion(
    db: AsyncSession, *, tenant_id: uuid.UUID | None = None
) -> tuple[int, int]:
    """`(total, enrolled)` course interests -- platform-wide when `tenant_id`
    is omitted (ADR-025/ADR-047's own metric, `make monetisation-metrics`),
    scoped to one provider when given (Sprint 39, BL-10.3's dashboard).

    One query, two callers: `scripts/report_conversion_metrics.py` calls this
    with no `tenant_id` rather than holding a second copy of the same count,
    the same reason `market_scarce_skills` has exactly one home.
    """
    total_stmt = select(func.count()).select_from(CourseInterest)
    enrolled_stmt = (
        select(func.count()).select_from(CourseInterest).where(CourseInterest.status == "enrolled")
    )
    if tenant_id is not None:
        total_stmt = total_stmt.join(Course, Course.id == CourseInterest.course_id).where(
            Course.tenant_id == tenant_id
        )
        enrolled_stmt = enrolled_stmt.join(Course, Course.id == CourseInterest.course_id).where(
            Course.tenant_id == tenant_id
        )
    total = await db.scalar(total_stmt)
    enrolled = await db.scalar(enrolled_stmt)
    return total or 0, enrolled or 0


@dataclass(frozen=True)
class ProviderDashboard:
    """A course provider's landing numbers (Sprint 39, BL-10.3) -- the direct
    payoff of ADR-047's `"enrolled"` status finally having a screen."""

    published_courses: int
    interested_live: int
    interested_total: int
    enrolled: int
    # `conversion_rate` computed once here, server-side, so a `ProgressRing`
    # never has to divide `enrolled / interested_total` on the client
    # (Sprint 40) -- and the per-course rows `counts_by_course()` already
    # fetched, which the sums above used to discard after adding up.
    conversion_rate: float = 0.0
    courses: list[tuple[Course, int, int]] = field(default_factory=list)


async def provider_dashboard(db: AsyncSession, tenant_id: uuid.UUID) -> ProviderDashboard:
    published = await db.scalar(
        select(func.count())
        .select_from(Course)
        .where(Course.tenant_id == tenant_id, Course.status == "published")
    )
    rows = await counts_by_course(db, tenant_id)
    interested_live = sum(live for _course, live, _total in rows)
    interested_total = sum(total for _course, _live, total in rows)
    total_interests, enrolled = await enrolment_conversion(db, tenant_id=tenant_id)
    return ProviderDashboard(
        published_courses=published or 0,
        interested_live=interested_live,
        interested_total=interested_total,
        enrolled=enrolled,
        conversion_rate=(enrolled / total_interests) if total_interests else 0.0,
        courses=rows,
    )


async def set_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    course_slug: str,
    interest_id: uuid.UUID,
    new_status: str,
) -> CourseInterest:
    """Move a learner's interest along: contacted, or enrolled.

    **The learner is told**, in-app only (Sprint 41, the owner's decision). This
    used to be deliberately silent, on the reasoning that the provider phones
    them, so a notice would arrive after the call it describes. But a call can
    be missed, and an enrolment recorded against somebody who never learns of it
    is a record they cannot check -- a free in-app notice costs nothing and
    reaches the phone-only learner an email never would. No email: this is not
    worth an inbox.
    """
    course = await _course_of(db, tenant_id, course_slug)
    # `FOR UPDATE`: the "withdrawn" check below must still hold when the write
    # lands, or a status change overwrites a withdrawal made at the same instant and
    # puts the learner's contact back on the provider's screen (Sprint 45).
    interest = await db.scalar(
        select(CourseInterest)
        .where(CourseInterest.id == interest_id, CourseInterest.course_id == course.id)
        .with_for_update(of=CourseInterest)
        .execution_options(populate_existing=True)
    )
    if interest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interest not found")
    if interest.status == "withdrawn":
        # The learner took it back. Moving it along would put their contact
        # details back on a provider's screen by a side door.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This interest has been withdrawn by the learner"
        )

    changed = interest.status != new_status
    interest.status = new_status
    if changed:
        profile = await db.get(CandidateProfile, interest.profile_id)
        learner = await db.get(User, profile.user_id) if profile is not None else None
        if learner is not None:
            await enqueue(
                db,
                recipient_kind="user",
                recipient_id=learner.id,
                channel="in_app",
                template="course_interest_status_changed",
                payload={
                    "course": course.title,
                    "organisation": cast(Tenant, course.tenant).name,
                    "status": new_status,
                    "path": "/interests",
                },
                locale=learner.preferred_locale,
            )
    await db.commit()
    await record(
        db,
        "course_interest_status_changed",
        subject_type="course",
        subject_id=course.id,
        # The status, never who it was about: a provider-side event names no
        # learner, the same rule the employer console's events follow.
        payload={"status": new_status},
    )
    return interest


async def set_status_and_reload(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    course_slug: str,
    interest_id: uuid.UUID,
    new_status: str,
) -> tuple[CourseInterest, CandidateProfile, User]:
    """Mark a learner contacted, and return the row the screen re-renders.

    The sibling of `applications.employer_service.set_status_and_reload`, and
    for the same reason: the route used to refetch the list and pick its row out
    with a bare `next(...)`, which raises `StopIteration` -- a RuntimeError and
    a 500 inside a coroutine -- if the row is ever filtered out.
    """
    interest = await set_status(db, tenant_id, course_slug, interest_id, new_status)
    _course, rows = await interested_learners(db, tenant_id, course_slug)
    for row in rows:
        if row[0].id == interest.id:
            return row
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Interest not found")
