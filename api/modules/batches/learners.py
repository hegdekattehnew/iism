"""The centre's side of an interest (Sprint 100, ADR-103, BL-18.7, BL-20.3): who wants this batch,
how long they have waited, and who has been answered.

**Who sees a learner** is ADR-103's decision 1, built as recommended: the centre that runs the
batch and its organisation's owners and admins (`BATCH_LEARNERS`), and nobody else. The route's
tenant is the organisation or the centre and `service._locked` scopes a batch to it, so a manager
reaches only their own centre's learners and a stranger gets the 404 of none; the seller of the
course never reaches this module at all (it sees counts: `service.of_my_courses`).

**Withdrawn keeps the fact and loses the person.** A withdrawn row is listed (the centre's history
does not silently rewrite itself) with no contact, and cannot be moved along: that would put a
learner's contact back on a screen by a side door (Sprint 24's rule). A status change locks the
batch row first, so a seat cannot be given twice by two staff at the same instant, and then the
learner's row, so a withdrawal and a mark at the same instant leave one outcome.
"""

import uuid
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import today_ist
from api.modules.analytics import record
from api.modules.batches.models import TAKEN_STATUSES, BatchInterest
from api.modules.batches.schemas import BatchLearnerContactOut, BatchLearnerOut, BatchLearnersOut
from api.modules.batches.service import _enrolled_of, _locked, get_batch
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, Course
from api.modules.notifications import enqueue

# The rank of "still to answer": an unanswered learner comes first, the one who has waited longest
# at the top, then the rest in the order they came.
_UNANSWERED = case((BatchInterest.status == "registered", 0), else_=1)


async def learners_of(db: AsyncSession, tenant: Tenant, batch_id: uuid.UUID) -> BatchLearnersOut:
    batch_out = await get_batch(db, tenant, batch_id)  # the 404 of none, scoped to the tenant
    rows = (
        await db.execute(
            select(BatchInterest, CandidateProfile, User)
            .join(CandidateProfile, CandidateProfile.id == BatchInterest.profile_id)
            .join(User, User.id == CandidateProfile.user_id)
            .where(BatchInterest.batch_id == batch_id)
            .order_by(_UNANSWERED, BatchInterest.created_at, BatchInterest.id)
        )
    ).all()
    items = [_learner(i, p, u) for i, p, u in rows]
    return BatchLearnersOut(batch=batch_out, items=items, total=len(items))


def _learner(interest: BatchInterest, profile: CandidateProfile, user: User) -> BatchLearnerOut:
    live = interest.status != "withdrawn"
    return BatchLearnerOut(
        interest_id=str(interest.id),
        status=interest.status,
        registered_at=interest.created_at,
        # What the learner wrote, where they are and how to reach them: while live only.
        message=interest.message if live else None,
        location_state=profile.location_state if live else None,
        location_district=profile.location_district if live else None,
        contact=(
            BatchLearnerContactOut(full_name=user.full_name, phone=user.phone, email=user.email)
            if live
            else None
        ),
    )


async def set_status(
    db: AsyncSession,
    tenant: Tenant,
    actor: User,
    batch_id: uuid.UUID,
    interest_id: uuid.UUID,
    new_status: str,
) -> BatchLearnersOut:
    """Mark a learner contacted, enrolled or attended, and tell them (in-app) when it changes."""
    batch = await _locked(
        db, tenant, batch_id
    )  # FOR UPDATE on the batch: seats are given one at a time
    if batch.status == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "This batch was cancelled")
    interest = await db.scalar(
        select(BatchInterest)
        .where(BatchInterest.id == interest_id, BatchInterest.batch_id == batch.id)
        .with_for_update(of=BatchInterest)
        .execution_options(populate_existing=True)
    )
    if interest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interest not found")
    if interest.status == "withdrawn":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This interest has been withdrawn by the learner"
        )
    taking = new_status in TAKEN_STATUSES and interest.status not in TAKEN_STATUSES
    if new_status == "attended":
        if interest.status not in TAKEN_STATUSES:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Mark the learner enrolled before marking them attended"
            )
        if batch.starts_on > today_ist():
            raise HTTPException(
                status.HTTP_409_CONFLICT, "This batch has not started, so nobody can have attended"
            )
    if taking:
        taken = await _enrolled_of(db, batch.id)
        if taken >= batch.seats:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Every seat is taken. Raise the seats, or free one, before enrolling another",
            )
    changed = interest.status != new_status
    interest.status = new_status
    if changed and new_status != "attended":
        profile = await db.get(CandidateProfile, interest.profile_id)
        learner = await db.get(User, profile.user_id) if profile is not None else None
        course = await db.get(Course, batch.course_id)
        centre = await db.get(Tenant, batch.centre_id)
        organisation = (
            await db.get(Tenant, centre.parent_id) if centre and centre.parent_id else None
        )
        if learner is not None and course is not None and organisation is not None:
            await enqueue(
                db,
                recipient_kind="user",
                recipient_id=learner.id,
                channel="in_app",
                template="batch_interest_status_changed",
                payload={
                    "course": course.title,
                    "organisation": organisation.name,
                    "status": new_status,
                    "path": "/interests",
                },
                locale=learner.preferred_locale,
            )
    organisation_id = cast(uuid.UUID, (await db.get(Tenant, batch.centre_id)).parent_id)  # type: ignore[union-attr]
    await db.commit()
    await record(
        db,
        "batch_interest_status_changed",
        user_id=actor.id,
        subject_type="tenant",
        subject_id=organisation_id,
        # The status, never who it was about.
        payload={"status": new_status},
    )
    return await learners_of(db, tenant, batch_id)
