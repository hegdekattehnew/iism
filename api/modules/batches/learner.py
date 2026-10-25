"""The learner's side of a batch (Sprint 100, ADR-103, BL-20.2, BL-20.3): find, register, withdraw.

**Finding.** The list is public. It shows batches a person can still join or has just missed
(`open` and `full`: a full batch is shown and labelled, because a learner should know there was
one), never a draft, a cancelled or a finished one, never one whose course is not live and never
one at a closed centre. The order is **reach, then the soonest start, then the fee, then the id**
(ADR-068's reach rule and its neutrality: an unknown place is neither promoted nor buried), and
**nothing is hidden by it**: a batch in another state is last, not gone. The order is computed in
the database so a page boundary never swaps rows, and `reach` is `attendance`'s own function read
over the same facts, so the label and the order cannot disagree (a test holds them equal).

**Registering** discloses the learner's name, phone, email, district and message to the centre that
runs the batch and to its organisation's owners and admins (ADR-103's decision 1, built as
recommended); never to the seller of the course, never to another centre. The learner chooses it,
the consent step names who receives it, and withdrawing takes it back. `require_not_paused` runs
first (ADR-082), the batch is share-locked so a cancellation and a registration at the same instant
cannot both win (the cancel takes `FOR UPDATE` and tells the learners it can see), and a first
registration has no row to lock, so the unique constraint is the arbiter (ADR-052).
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, and_, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.core.clock import today_ist
from api.core.config import get_settings
from api.modules.analytics import record
from api.modules.batches import phases
from api.modules.batches.models import TAKEN_STATUSES, Batch, BatchInterest
from api.modules.batches.schemas import (
    BatchCentreOut,
    BatchCourseOut,
    BatchInterestOut,
    MyInterestRef,
    PublicBatchList,
    PublicBatchOut,
)
from api.modules.batches.service import _enrolled, _org_ref
from api.modules.identity import User, require_not_paused
from api.modules.identity.models import Tenant
from api.modules.marketplace import ensure_profile
from api.modules.marketplace.models import CandidateProfile, Course
from api.modules.matching import AttendContext, attend_context
from api.modules.matching.attendance import REACH_RANK, CourseFacts, Reach, assess
from api.modules.notifications import enqueue

log = structlog.get_logger("iism.batches")

PAGE_MAX = 100


def _public_conditions(centre: type[Tenant]) -> list[ColumnElement[bool]]:
    """What the public list may show, before the phase: published, at an open centre, of a course
    that is live. (Not over is implied by not started, which the list also requires.)"""
    return [
        Batch.status == "published",
        centre.closed_at.is_(None),
        Course.status == "published",
        Course.taken_down_at.is_(None),
    ]


def _facts(batch: Batch, centre: Tenant) -> CourseFacts:
    return CourseFacts(
        mode="online" if batch.mode == "online" else "offline",
        state_id=centre.state_id,
        district_id=centre.district_id,
        starts_on=None,
        seats_left=None,
        fee_inr=None,
    )


def _reach_rank(centre: type[Tenant], context: AttendContext | None) -> ColumnElement[int]:
    """`attendance._reach` as SQL, so the page order is the label's order."""
    states = context.states if context else frozenset()
    districts = context.districts if context else frozenset()
    unknown = REACH_RANK["unknown"]
    online = Batch.mode == "online"
    no_place = and_(centre.state_id.is_(None), centre.district_id.is_(None))
    whens = [(online, REACH_RANK["online"]), (no_place, unknown)]
    if not states and not districts:
        return case(*whens, else_=unknown)
    if districts:
        whens.append((centre.district_id.in_(districts), REACH_RANK["district"]))
    if states:
        whens.append((centre.state_id.in_(states), REACH_RANK["state"]))
    return case(*whens, else_=REACH_RANK["elsewhere"])


async def _context(
    db: AsyncSession, user: User | None, state_id: uuid.UUID | None, district_id: uuid.UUID | None
) -> tuple[AttendContext | None, uuid.UUID | None]:
    """Where the person is: their profile's places if signed in, else what they asked about."""
    profile_id = None
    if user is not None:
        # Read, never created: an organisation-only account that opens the public list must not be
        # given a candidate profile by looking (ADR-038's lesson, the career page's rule).
        profile_id = await db.scalar(
            select(CandidateProfile.id).where(CandidateProfile.user_id == user.id)
        )
        if profile_id is not None:
            context = await attend_context(db, profile_id)
            if context.states or context.districts:
                return context, profile_id
    if state_id or district_id:
        return (
            AttendContext(
                states=frozenset({state_id}) if state_id else frozenset(),
                districts=frozenset({district_id}) if district_id else frozenset(),
                budget_inr=None,
                today=today_ist(),
            ),
            profile_id,
        )
    return None, profile_id


def _out(
    batch: Batch,
    course: Course,
    centre: Tenant,
    organisation: Tenant,
    provider: Tenant,
    *,
    enrolled: int,
    mine: tuple[uuid.UUID, str] | None,
    context: AttendContext | None,
    today: date,
) -> PublicBatchOut:
    reach: Reach = (
        assess(_facts(batch, centre), context).reach
        if context is not None
        else ("online" if batch.mode == "online" else "unknown")
    )
    return PublicBatchOut(
        id=str(batch.id),
        course=BatchCourseOut(
            slug=course.slug,
            title=course.title,
            fee_inr=course.fee_inr,
            available=course.status == "published" and course.taken_down_at is None,
            provider=_org_ref(provider),
            own=provider.id == organisation.id,
        ),
        centre=BatchCentreOut(
            slug=centre.slug,
            name=centre.name,
            location_state=centre.location_state,
            location_district=centre.location_district,
            is_verified=centre.is_verified,
        ),
        organisation=_org_ref(organisation),
        label=batch.label,
        starts_on=batch.starts_on,
        ends_on=batch.ends_on,
        seats=batch.seats,
        seats_left=phases.seats_left(seats=batch.seats, enrolled=enrolled),
        mode=batch.mode,
        schedule=batch.schedule,
        fee_effective=batch.fee_inr if batch.fee_inr is not None else course.fee_inr,
        fee_is_override=batch.fee_inr is not None,
        phase=phases.phase(
            status=batch.status,
            starts_on=batch.starts_on,
            ends_on=batch.ends_on,
            seats=batch.seats,
            enrolled=enrolled,
            today=today,
        ),
        cancel_reason=batch.cancel_reason,
        reach=reach,
        my_interest=MyInterestRef(id=str(mine[0]), status=mine[1]) if mine else None,
    )


async def _rows(
    db: AsyncSession,
    conditions: list[ColumnElement[bool]],
    *,
    profile_id: uuid.UUID | None,
    context: AttendContext | None,
    centre: type[Tenant],
    order: Sequence[Any] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[PublicBatchOut]:
    organisation = aliased(Tenant)
    provider = aliased(Tenant)
    enrolled = _enrolled().label("enrolled")
    query = (
        select(Batch, Course, centre, organisation, provider, enrolled)
        .join(Course, Course.id == Batch.course_id)
        .join(centre, centre.id == Batch.centre_id)
        .join(organisation, organisation.id == centre.parent_id)
        .join(provider, provider.id == Course.tenant_id)
        .where(*conditions)
    )
    if order:
        query = query.order_by(*order)
    if limit is not None:
        query = query.limit(limit).offset(offset)
    rows = (await db.execute(query)).all()
    mine: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
    if profile_id is not None and rows:
        found = await db.execute(
            select(BatchInterest.batch_id, BatchInterest.id, BatchInterest.status).where(
                BatchInterest.profile_id == profile_id,
                BatchInterest.batch_id.in_([r[0].id for r in rows]),
                BatchInterest.status != "withdrawn",
            )
        )
        mine = {b: (i, s) for b, i, s in found.all()}
    today = today_ist()
    return [
        _out(
            b, c, ce, o, p, enrolled=int(e or 0), mine=mine.get(b.id), context=context, today=today
        )
        for b, c, ce, o, p, e in rows
    ]


async def list_public(
    db: AsyncSession,
    user: User | None,
    *,
    state_id: uuid.UUID | None,
    district_id: uuid.UUID | None,
    starts_within: int | None,
    max_fee: int | None,
    course_slug: str | None,
    mode: str | None,
    limit: int,
    offset: int,
) -> PublicBatchList:
    limit = max(1, min(limit, PAGE_MAX))
    today = today_ist()
    centre = aliased(Tenant)
    context, profile_id = await _context(db, user, state_id, district_id)
    conditions = _public_conditions(centre)
    # Joinable or just filled: a batch that has started is neither (it is not "next").
    conditions.append(Batch.starts_on > today)
    if state_id is not None:
        conditions.append(centre.state_id == state_id)
    if district_id is not None:
        conditions.append(centre.district_id == district_id)
    if starts_within is not None:
        conditions.append(Batch.starts_on <= today + timedelta(days=starts_within))
    fee = func.coalesce(Batch.fee_inr, Course.fee_inr, 0)
    if max_fee is not None:
        conditions.append(fee <= max_fee)
    if course_slug is not None:
        conditions.append(Course.slug == course_slug)
    if mode is not None:
        conditions.append(Batch.mode == mode)
    total_query = (
        select(func.count())
        .select_from(Batch)
        .join(Course, Course.id == Batch.course_id)
        .join(centre, centre.id == Batch.centre_id)
        .where(*conditions)
    )
    total = (await db.scalar(total_query)) or 0
    items = await _rows(
        db,
        conditions,
        profile_id=profile_id,
        context=context,
        centre=centre,
        order=[_reach_rank(centre, context), Batch.starts_on, fee, Batch.id],
        limit=limit,
        offset=offset,
    )
    return PublicBatchList(items=items, total=total, limit=limit, offset=offset)


async def get_public(db: AsyncSession, user: User | None, batch_id: uuid.UUID) -> PublicBatchOut:
    """One batch, for a link a learner holds. A cancelled one is still shown (as cancelled: people
    have it bookmarked), a draft, or one whose course is no longer live, or at a closed centre, is
    the 404 of none."""
    centre = aliased(Tenant)
    context, profile_id = await _context(db, user, None, None)
    conditions = [
        Batch.id == batch_id,
        Batch.status.in_(("published", "cancelled")),
        Course.status == "published",
        Course.taken_down_at.is_(None),
        centre.closed_at.is_(None),
    ]
    rows = await _rows(db, conditions, profile_id=profile_id, context=context, centre=centre)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return rows[0]


# --------------------------------------------------------------------------- registering


async def _within_daily_cap(db: AsyncSession, profile_id: uuid.UUID) -> None:
    """Refuse a learner who is spraying: the same limit, counted the same way, as a course's."""
    limit = get_settings().max_course_interests_per_day
    since = datetime.now(UTC) - timedelta(days=1)
    made = await db.scalar(
        select(func.count())
        .select_from(BatchInterest)
        .where(BatchInterest.profile_id == profile_id, BatchInterest.created_at >= since)
    )
    if (made or 0) >= limit:
        log.warning("batch_interest.daily_cap_reached", limit=limit)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You have registered interest in a lot of batches today. Try again tomorrow.",
            headers={"retry-after": "3600"},
        )


async def register(
    db: AsyncSession, user: User, *, batch_id: uuid.UUID, message: str | None = None
) -> BatchInterestOut:
    profile = await ensure_profile(db, user.id)
    # Registering shares contact with a centre: stopped outright by a withdrawal of consent, under
    # a shared row lock (ADR-082).
    await require_not_paused(db, user)
    await _within_daily_cap(db, profile.id)

    # Share-locked and re-read: a cancellation takes `FOR UPDATE` and tells the learners it can
    # see, so a registration either lands before it (and is told) or finds the batch cancelled.
    batch = await db.scalar(
        select(Batch)
        .where(Batch.id == batch_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    course = await db.get(Course, batch.course_id) if batch is not None else None
    centre = await db.get(Tenant, batch.centre_id) if batch is not None else None
    organisation = await db.get(Tenant, centre.parent_id) if centre and centre.parent_id else None
    if batch is None or course is None or centre is None or organisation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    if batch.status != "published" or course.status != "published" or course.taken_down_at:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    enrolled = (
        await db.scalar(
            select(func.count())
            .select_from(BatchInterest)
            .where(BatchInterest.batch_id == batch.id, BatchInterest.status.in_(TAKEN_STATUSES))
        )
    ) or 0
    now_phase = phases.phase(
        status=batch.status,
        starts_on=batch.starts_on,
        ends_on=batch.ends_on,
        seats=batch.seats,
        enrolled=enrolled,
        today=today_ist(),
    )
    if centre.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This centre is closed")
    if now_phase != "open":
        said = {"full": "This batch is full", "running": "This batch has already started"}
        raise HTTPException(
            status.HTTP_409_CONFLICT, said.get(now_phase, "This batch can no longer be joined")
        )

    existing = await db.scalar(
        select(BatchInterest)
        .where(BatchInterest.batch_id == batch.id, BatchInterest.profile_id == profile.id)
        .with_for_update(of=BatchInterest)
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    if existing is not None and existing.status != "withdrawn":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You have already registered interest in this batch"
        )
    if existing is not None:
        existing.status = "registered"
        existing.contact_shared_at = now
        existing.contact_revoked_at = None
        if message is not None:
            existing.message = message
        interest = existing
    else:
        interest = BatchInterest(
            batch_id=batch.id, profile_id=profile.id, message=message, contact_shared_at=now
        )
        try:
            async with db.begin_nested():
                db.add(interest)
                await db.flush()
        except IntegrityError:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "You have already registered interest in this batch"
            ) from None

    # In the same transaction, to the organisation (a name, the centre and a link, nothing about
    # the learner): who wants it belongs behind the sign-in.
    await enqueue(
        db,
        recipient_kind="tenant",
        recipient_id=organisation.id,
        channel="email",
        template="batch_interest_registered",
        payload={
            "course": course.title,
            "centre": centre.name,
            "path": f"/employer/{organisation.slug}/batches",
        },
    )
    interest_id = interest.id
    org_id, provider_id, batch_key = organisation.id, course.tenant_id, batch.id
    await db.commit()
    await record(
        db,
        "batch_interest_registered",
        user_id=user.id,
        subject_type="batch",
        subject_id=batch_key,
        # Both parties' ids, never a person: conversion is attributable to the seller or to the
        # organisation that ran the class (ADR-025, ADR-103).
        payload={"organisation": str(org_id), "provider": str(provider_id)},
    )
    return await _mine(db, user, interest_id)


async def _mine(db: AsyncSession, user: User, interest_id: uuid.UUID) -> BatchInterestOut:
    profile = await ensure_profile(db, user.id)
    interest = await db.scalar(
        select(BatchInterest)
        .where(BatchInterest.id == interest_id, BatchInterest.profile_id == profile.id)
        .execution_options(populate_existing=True)
    )
    if interest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interest not found")
    centre = aliased(Tenant)
    context, _ = await _context(db, user, None, None)
    rows = await _rows(
        db,
        [Batch.id == interest.batch_id],
        profile_id=profile.id,
        context=context,
        centre=centre,
    )
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return BatchInterestOut(
        id=str(interest.id),
        batch=rows[0],
        status=interest.status,
        message=interest.message,
        registered_at=interest.created_at,
        updated_at=interest.updated_at,
    )


async def list_mine(db: AsyncSession, user: User) -> list[BatchInterestOut]:
    profile = await ensure_profile(db, user.id)
    ids = (
        await db.scalars(
            select(BatchInterest.id)
            .where(BatchInterest.profile_id == profile.id)
            .order_by(BatchInterest.created_at.desc(), BatchInterest.id)
            .limit(200)
        )
    ).all()
    return [await _mine(db, user, i) for i in ids]


async def withdraw(db: AsyncSession, user: User, interest_id: uuid.UUID) -> BatchInterestOut:
    """Take it back, and the contact details with it. Unconditional: a learner's withdrawal is
    always the last word, and the centre's side locks the row and refuses a withdrawn one."""
    profile = await ensure_profile(db, user.id)
    interest = await db.scalar(
        select(BatchInterest).where(
            BatchInterest.id == interest_id, BatchInterest.profile_id == profile.id
        )
    )
    if interest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interest not found")
    if interest.status != "withdrawn":
        interest.status = "withdrawn"
        interest.contact_revoked_at = datetime.now(UTC)
        batch_id = interest.batch_id
        await db.commit()
        await record(
            db,
            "batch_interest_withdrawn",
            user_id=user.id,
            subject_type="batch",
            subject_id=batch_id,
        )
    return await _mine(db, user, interest_id)


async def live_interests(db: AsyncSession, user: User) -> list[BatchInterest]:
    """The caller's interests whose contact a centre can still see."""
    profile = await ensure_profile(db, user.id)
    rows = await db.scalars(
        select(BatchInterest).where(
            BatchInterest.profile_id == profile.id, BatchInterest.status != "withdrawn"
        )
    )
    return list(rows.all())


async def withdraw_all_live(db: AsyncSession, user: User) -> int:
    done = 0
    for interest in await live_interests(db, user):
        await withdraw(db, user, interest.id)
        done += 1
    return done


__all__ = [
    "get_public",
    "list_mine",
    "list_public",
    "live_interests",
    "register",
    "withdraw",
    "withdraw_all_live",
]
