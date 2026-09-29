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

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import record
from api.modules.identity.models import User
from api.modules.interests.models import LIVE_STATUSES, CourseInterest
from api.modules.marketplace.models import CandidateProfile, Course


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


async def set_status(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    course_slug: str,
    interest_id: uuid.UUID,
    new_status: str,
) -> CourseInterest:
    """Mark that the provider has been in touch.

    Deliberately silent to the learner: the provider reaches them by phone,
    which is the entire point of the disclosure, so a notification saying
    "somebody contacted you" would arrive after the call it describes.
    """
    course = await _course_of(db, tenant_id, course_slug)
    interest = await db.scalar(
        select(CourseInterest).where(
            CourseInterest.id == interest_id, CourseInterest.course_id == course.id
        )
    )
    if interest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interest not found")
    if interest.status == "withdrawn":
        # The learner took it back. Moving it along would put their contact
        # details back on a provider's screen by a side door.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This interest has been withdrawn by the learner"
        )

    interest.status = new_status
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
