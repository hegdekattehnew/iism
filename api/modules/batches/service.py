"""Batches: making one, publishing it, cancelling it (Sprint 98, ADR-103, BL-18.5).

The rules held here, each in one place:

- **A batch is made only for a course the organisation may deliver**: its own, or one it holds an
  approved, unended authorisation for (`delivery.authorises`). Asked at creation **and again at
  publication, under a share lock on the authorisation rows**, because the answer is only true while
  nobody can end it: `revoke` takes `FOR UPDATE` on the same rows, so a batch either exists before
  the revocation's sweep looks (and is cancelled by it) or finds the arrangement ended (and is
  refused).
- **A centre that is closed gets no new batch**, and a centre cannot close with a live batch
  (`live_at_centre`, asked by the centre writer). The centre row is share-locked here and
  update-locked there, for the same reason.
- **Nothing here stops a class in progress.** A running batch is never cancelled by a side effect:
  revoking an arrangement cancels only the batches that have not started (and drafts), and the
  running ones finish.
- **What a batch *is* now is derived** (`phases.phase`), seats left included. Cancelling tells the
  learners who had registered, in fixed words, through the outbox, in the cancelling act's own
  transaction (`enqueue_many`), so a crash cannot cancel without telling or tell without cancelling.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import structlog
from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, ScalarSelect, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.core.clock import today_ist
from api.modules.analytics import record
from api.modules.batches import phases
from api.modules.batches.models import (
    LIVE_INTEREST_STATUSES,
    Batch,
    BatchInterest,
)
from api.modules.batches.schemas import (
    BatchCentreOut,
    BatchCourseOut,
    BatchFields,
    BatchIn,
    BatchList,
    BatchOrgOut,
    BatchOut,
    BatchOverview,
    BatchUpdateIn,
    CourseBatchesOut,
    CourseBatchesRowOut,
    DeliverableCourseOut,
    DeliverableCourses,
    OrgCourseRef,
)
from api.modules.delivery import CourseDeliveryAuthorisation, authorises
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, Course
from api.modules.notifications import enqueue_many

log = structlog.get_logger("iism.batches")

# A cap that deters a script, not a promise (the convention): batches a centre can hold that are
# not yet over or cancelled. Finished and cancelled ones are history and do not count.
MAX_LIVE_PER_CENTRE = 300
PAGE_MAX = 100
COURSES_MAX = 500


# ------------------------------------------------------------------------------ reading


def _enrolled() -> ScalarSelect[int]:
    return (
        select(func.count())
        .where(BatchInterest.batch_id == Batch.id, BatchInterest.status == "enrolled")
        .scalar_subquery()
    )


def _interested() -> ScalarSelect[int]:
    return (
        select(func.count())
        .where(
            BatchInterest.batch_id == Batch.id,
            BatchInterest.status.in_(LIVE_INTEREST_STATUSES),
        )
        .scalar_subquery()
    )


def _phase_clause(name: str, enrolled: ScalarSelect[int], today: date) -> ColumnElement[bool]:
    """The SQL twin of `phases.phase`, so a filtered `total` is counted where the rows are. A test
    holds the two equal over every phase."""
    published = Batch.status == "published"
    if name == "draft":
        return Batch.status == "draft"
    if name == "cancelled":
        return Batch.status == "cancelled"
    if name == "finished":
        return and_(published, Batch.ends_on < today)
    if name == "running":
        return and_(published, Batch.starts_on <= today, Batch.ends_on >= today)
    if name == "open":
        return and_(published, Batch.starts_on > today, enrolled < Batch.seats)
    if name == "full":
        return and_(published, Batch.starts_on > today, enrolled >= Batch.seats)
    raise ValueError(f"unknown phase {name!r}")


def _org_ref(tenant: Tenant) -> BatchOrgOut:
    return BatchOrgOut(slug=tenant.slug, name=tenant.name, is_verified=tenant.is_verified)


def out_of(
    batch: Batch,
    course: Course,
    centre: Tenant,
    organisation: Tenant,
    provider: Tenant,
    *,
    enrolled: int,
    interested: int,
    today: date,
) -> BatchOut:
    return BatchOut(
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
        enrolled=enrolled,
        seats_left=phases.seats_left(seats=batch.seats, enrolled=enrolled),
        interested=interested,
        mode=batch.mode,
        schedule=batch.schedule,
        fee_inr=batch.fee_inr,
        fee_effective=batch.fee_inr if batch.fee_inr is not None else course.fee_inr,
        fee_is_override=batch.fee_inr is not None,
        status=batch.status,
        phase=phases.phase(
            status=batch.status,
            starts_on=batch.starts_on,
            ends_on=batch.ends_on,
            seats=batch.seats,
            enrolled=enrolled,
            today=today,
        ),
        cancel_reason=batch.cancel_reason,
        published_at=batch.published_at,
        cancelled_at=batch.cancelled_at,
        created_at=batch.created_at,
    )


def _scope(tenant: Tenant) -> ColumnElement[bool]:
    """Which centres this tenant reaches: all of an organisation's, or only the centre itself."""
    if tenant.tenant_type == "training_centre":
        return Batch.centre_id == tenant.id
    return Batch.centre_id.in_(select(Tenant.id).where(Tenant.parent_id == tenant.id))


async def _select(
    db: AsyncSession,
    tenant: Tenant,
    *conditions: ColumnElement[bool],
    limit: int | None = None,
    offset: int = 0,
    soonest_first: bool = False,
) -> list[BatchOut]:
    centre = aliased(Tenant)
    organisation = aliased(Tenant)
    provider = aliased(Tenant)
    enrolled = _enrolled().label("enrolled")
    interested = _interested().label("interested")
    query = (
        select(Batch, Course, centre, organisation, provider, enrolled, interested)
        .join(Course, Course.id == Batch.course_id)
        .join(centre, centre.id == Batch.centre_id)
        .join(organisation, organisation.id == centre.parent_id)
        .join(provider, provider.id == Course.tenant_id)
        .where(_scope(tenant), *conditions)
        # The furthest start first (what was planned most recently ahead is on top); ends in the id,
        # so a page boundary never swaps rows.
        .order_by(Batch.starts_on if soonest_first else Batch.starts_on.desc(), Batch.id)
    )
    if limit is not None:
        query = query.limit(limit).offset(offset)
    today = today_ist()
    rows = (await db.execute(query)).all()
    return [
        out_of(b, c, ce, o, p, enrolled=int(e or 0), interested=int(i or 0), today=today)
        for b, c, ce, o, p, e, i in rows
    ]


async def list_batches(
    db: AsyncSession,
    tenant: Tenant,
    *,
    phase: str | None,
    centre_slug: str | None,
    course_slug: str | None,
    limit: int,
    offset: int,
) -> BatchList:
    limit = max(1, min(limit, PAGE_MAX))
    today = today_ist()
    conditions = []
    if phase is not None:
        conditions.append(_phase_clause(phase, _enrolled(), today))
    if centre_slug is not None:
        conditions.append(Batch.centre_id.in_(select(Tenant.id).where(Tenant.slug == centre_slug)))
    if course_slug is not None:
        conditions.append(Batch.course_id.in_(select(Course.id).where(Course.slug == course_slug)))
    total = (
        await db.scalar(select(func.count()).select_from(Batch).where(_scope(tenant), *conditions))
    ) or 0
    items = await _select(db, tenant, *conditions, limit=limit, offset=offset)
    return BatchList(items=items, total=total, limit=limit, offset=offset)


async def get_batch(db: AsyncSession, tenant: Tenant, batch_id: uuid.UUID) -> BatchOut:
    items = await _select(db, tenant, Batch.id == batch_id)
    if not items:
        # One answer for a missing batch and another organisation's (ADR-038).
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return items[0]


async def deliverable_courses(db: AsyncSession, tenant: Tenant) -> DeliverableCourses:
    """The courses this organisation may make a batch of: its own published ones, and those of a
    seller that has authorised it (one course, or all). A centre asks for its organisation's."""
    from api.modules.delivery.models import CourseDeliveryAuthorisation as Auth

    org_id = tenant.parent_id if tenant.tenant_type == "training_centre" else tenant.id
    provider = aliased(Tenant)
    authorised = (
        select(Auth.id)
        .where(
            Auth.partner_id == org_id,
            Auth.provider_id == Course.tenant_id,
            or_(Auth.course_id.is_(None), Auth.course_id == Course.id),
            Auth.approved_at.is_not(None),
            Auth.ended_at.is_(None),
        )
        .exists()
    )
    rows = (
        await db.execute(
            select(Course, provider)
            .join(provider, provider.id == Course.tenant_id)
            .where(
                Course.status == "published",
                Course.taken_down_at.is_(None),
                or_(Course.tenant_id == org_id, authorised),
            )
            .order_by(Course.title, Course.id)
            .limit(COURSES_MAX)
        )
    ).all()
    items = [
        DeliverableCourseOut(
            slug=c.slug,
            title=c.title,
            fee_inr=c.fee_inr,
            provider=_org_ref(p),
            own=p.id == org_id,
        )
        for c, p in rows
    ]
    return DeliverableCourses(items=items, total=len(items))


SOON_DAYS = 7
FILLING_DAYS = 14


async def overview(db: AsyncSession, tenant: Tenant) -> BatchOverview:
    """The home's figures: what is waiting to be published, what starts this week, what is running,
    how many seats are still free in classes that begin within a fortnight, and what needs a look.

    Counted in one pass over the batches that are not over (a draft, a published one not yet ended),
    in the database, with the same predicates the list filters by; the next few that start are the
    list's own rows, soonest first.
    """
    today = today_ist()
    soon = today + timedelta(days=SOON_DAYS)
    filling = today + timedelta(days=FILLING_DAYS)
    enrolled = _enrolled()
    published = Batch.status == "published"
    row = (
        await db.execute(
            select(
                func.count().filter(Batch.status == "draft"),
                func.count().filter(published, Batch.starts_on > today, Batch.starts_on <= soon),
                func.count().filter(published, Batch.starts_on <= today),
                func.coalesce(
                    func.sum(Batch.seats - enrolled).filter(
                        published, Batch.starts_on > today, Batch.starts_on <= filling
                    ),
                    0,
                ),
                func.count().filter(
                    published,
                    Batch.starts_on > today,
                    Batch.starts_on <= filling,
                    enrolled < Batch.seats,
                ),
                func.count().filter(
                    Batch.course_id.in_(
                        select(Course.id).where(
                            or_(Course.status != "published", Course.taken_down_at.is_not(None))
                        )
                    )
                ),
            )
            .select_from(Batch)
            .where(
                _scope(tenant),
                Batch.status.in_(("draft", "published")),
                Batch.ends_on >= today,
            )
        )
    ).one()
    upcoming = await _select(
        db,
        tenant,
        published,
        Batch.starts_on > today,
        limit=5,
        soonest_first=True,
    )
    drafts, starting, running, seats, batches_with_seats, unavailable = row
    return BatchOverview(
        drafts=drafts,
        starting_soon=starting,
        running=running,
        unfilled_seats=max(0, int(seats or 0)),
        unfilled_batches=batches_with_seats,
        unavailable=unavailable,
        upcoming=upcoming,
    )


async def of_my_courses(db: AsyncSession, seller: Tenant) -> CourseBatchesOut:
    """The seller's read-only view: how its courses are being run by others, **counts and nothing
    else** (ADR-103's recommendation). A draft is the other organisation's private plan, so only
    published batches are counted; no learner, contact or centre is named. Its own organisation's
    batches of its own courses are included, because they are batches of its courses too."""
    centre = aliased(Tenant)
    organisation = aliased(Tenant)
    enrolled = _enrolled().label("enrolled")
    rows = (
        await db.execute(
            select(Batch, Course, organisation, enrolled)
            .join(Course, Course.id == Batch.course_id)
            .join(centre, centre.id == Batch.centre_id)
            .join(organisation, organisation.id == centre.parent_id)
            .where(Course.tenant_id == seller.id, Batch.status == "published")
            .order_by(Course.title, organisation.name, Batch.id)
            .limit(5000)
        )
    ).all()
    today = today_ist()
    grouped: dict[tuple[uuid.UUID, uuid.UUID], CourseBatchesRowOut] = {}
    for batch, course, org, enrolled_count in rows:
        key = (course.id, org.id)
        item = grouped.get(key)
        if item is None:
            item = grouped[key] = CourseBatchesRowOut(
                course=OrgCourseRef(slug=course.slug, title=course.title),
                organisation=_org_ref(org),
                batches=0,
                open=0,
                full=0,
                running=0,
                finished=0,
                seats=0,
                enrolled=0,
            )
        enrolled_count = int(enrolled_count or 0)
        item.batches += 1
        item.seats += batch.seats
        item.enrolled += enrolled_count
        now = phases.phase(
            status=batch.status,
            starts_on=batch.starts_on,
            ends_on=batch.ends_on,
            seats=batch.seats,
            enrolled=enrolled_count,
            today=today,
        )
        if now in ("open", "full", "running", "finished"):
            setattr(item, now, getattr(item, now) + 1)
    items = list(grouped.values())
    return CourseBatchesOut(items=items, total=len(items))


async def live_at_centre(db: AsyncSession, centre_id: uuid.UUID) -> int:
    """Batches at a centre not yet over or cancelled (drafts too): what keeps it open."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(Batch)
            .where(
                Batch.centre_id == centre_id,
                Batch.status.in_(("draft", "published")),
                Batch.ends_on >= today_ist(),
            )
        )
    ) or 0


async def live_for_course(db: AsyncSession, course_id: uuid.UUID) -> int:
    """The same for a course: what stops it being deleted from under a class."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(Batch)
            .where(
                Batch.course_id == course_id,
                Batch.status.in_(("draft", "published")),
                Batch.ends_on >= today_ist(),
            )
        )
    ) or 0


# ------------------------------------------------------------------------------ writing


async def _resolve_centre(db: AsyncSession, tenant: Tenant, centre_slug: str | None) -> Tenant:
    """The centre a new batch goes to, **inside what this tenant reaches**.

    A centre's own manager acts in the centre (and may name only it); an organisation names one of
    its centres. A centre of another organisation is the same 404 as a slug that is not there.
    """
    if tenant.tenant_type == "training_centre":
        if centre_slug not in (None, tenant.slug):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
        return tenant
    if centre_slug is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Say which centre it is at")
    centre = await db.scalar(
        select(Tenant).where(
            Tenant.slug == centre_slug,
            Tenant.tenant_type == "training_centre",
            Tenant.parent_id == tenant.id,
        )
    )
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    return centre


async def _lock_centre_open(db: AsyncSession, centre_id: uuid.UUID) -> Tenant:
    """Share-lock the centre and read it again: `close_centre` takes `FOR NO KEY UPDATE` and counts
    live batches, so a batch made at the same instant is either counted (the close is refused) or
    finds the centre closed (and is refused here)."""
    centre = await db.scalar(
        select(Tenant)
        .where(Tenant.id == centre_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if centre is None or centre.closed_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This centre is closed. Reopen it to plan a batch there"
        )
    return centre


async def _course_to_deliver(db: AsyncSession, slug: str) -> Course:
    course = await db.scalar(select(Course).where(Course.slug == slug))
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return course


def _refuse_unavailable(course: Course) -> None:
    if course.status != "published" or course.taken_down_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This course is not published, so it cannot be offered as a batch",
        )


async def _require_may_deliver(
    db: AsyncSession, organisation_id: uuid.UUID, course: Course
) -> None:
    """The writer's invariant, under lock: the organisation owns the course or holds an approval."""
    if not await authorises(db, organisation_id, course, lock=True):
        # 403 and the same sentence whether the course exists elsewhere or not: an organisation is
        # told what it needs to do, not whose course it guessed.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This organisation is not authorised to deliver that course. Ask the organisation "
            "that sells it to approve you first",
        )


async def add_batch(
    db: AsyncSession, centre_id: uuid.UUID, course: Course, actor_id: uuid.UUID, data: BatchFields
) -> Batch:
    """Insert one draft batch and flush. **Does not commit**: one creation commits, a file of them
    commits once. Every refusal is here so both paths make them: the centre is share-locked and
    open, the organisation may deliver the course (under lock), the course is live and the centre
    has room."""
    centre = await _lock_centre_open(db, centre_id)
    organisation_id = centre.parent_id
    assert (
        organisation_id is not None
    )  # a centre always has a parent (ck_tenants_centre_has_parent)
    await _require_may_deliver(db, organisation_id, course)
    _refuse_unavailable(course)
    if await live_at_centre(db, centre.id) >= MAX_LIVE_PER_CENTRE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A centre can have up to {MAX_LIVE_PER_CENTRE} batches that are not over. "
            "Cancel one that will not run, or write to us if you need more",
        )
    batch = Batch(
        course_id=course.id,
        centre_id=centre.id,
        label=data.label,
        starts_on=data.starts_on,
        ends_on=data.ends_on,
        seats=data.seats,
        mode=data.mode,
        schedule=data.schedule,
        fee_inr=data.fee_inr,
        status="draft",
        created_by=actor_id,
    )
    db.add(batch)
    await db.flush()
    return batch


async def create_batch(db: AsyncSession, tenant: Tenant, actor: User, data: BatchIn) -> BatchOut:
    centre = await _resolve_centre(db, tenant, data.centre_slug)
    course = await _course_to_deliver(db, data.course_slug)
    organisation_id = centre.parent_id
    batch = await add_batch(db, centre.id, course, actor.id, data)
    batch_id = batch.id
    await db.commit()
    # After the commit, never inside it: `record()` commits.
    await record(
        db,
        "batch_created",
        user_id=actor.id,
        subject_type="tenant",
        subject_id=organisation_id,
        payload={"own": course.tenant_id == organisation_id},
    )
    return await get_batch(db, tenant, batch_id)


async def _locked(db: AsyncSession, tenant: Tenant, batch_id: uuid.UUID) -> Batch:
    """The batch, locked and re-read, **if this tenant reaches it** (else the 404 of none)."""
    batch = await db.scalar(
        select(Batch)
        .where(Batch.id == batch_id, _scope(tenant))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return batch


async def _enrolled_of(db: AsyncSession, batch_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(BatchInterest)
            .where(BatchInterest.batch_id == batch_id, BatchInterest.status == "enrolled")
        )
    ) or 0


async def _live_interest_of(db: AsyncSession, batch_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(BatchInterest)
            .where(
                BatchInterest.batch_id == batch_id,
                BatchInterest.status.in_(LIVE_INTEREST_STATUSES),
            )
        )
    ) or 0


async def update_batch(
    db: AsyncSession, tenant: Tenant, batch_id: uuid.UUID, data: BatchUpdateIn
) -> BatchOut:
    batch = await _locked(db, tenant, batch_id)
    enrolled = await _enrolled_of(db, batch.id)
    today = today_ist()
    now = phases.phase(
        status=batch.status,
        starts_on=batch.starts_on,
        ends_on=batch.ends_on,
        seats=batch.seats,
        enrolled=enrolled,
        today=today,
    )
    if now not in phases.CANCELLABLE:
        # A running batch is a class in progress, and a finished or cancelled one is history.
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"A batch that is {now} can no longer be changed"
        )
    if data.seats < enrolled:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{enrolled} learners are already enrolled, so there cannot be fewer seats than that",
        )
    moves = (data.starts_on, data.ends_on) != (batch.starts_on, batch.ends_on)
    if moves and batch.status == "published" and await _live_interest_of(db, batch.id):
        # Learners registered for these dates; moving them is cancelling and making a new batch,
        # which tells them.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Learners have already registered for these dates. Cancel this batch and make a new "
            "one, so they are told",
        )
    batch.label = data.label
    batch.starts_on = data.starts_on
    batch.ends_on = data.ends_on
    batch.seats = data.seats
    batch.mode = data.mode
    batch.schedule = data.schedule
    batch.fee_inr = data.fee_inr
    await db.commit()
    return await get_batch(db, tenant, batch_id)


async def publish_batch(
    db: AsyncSession, tenant: Tenant, actor: User, batch_id: uuid.UUID
) -> BatchOut:
    batch = await _locked(db, tenant, batch_id)
    if batch.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This batch is already {batch.status}")
    centre = await _lock_centre_open(db, batch.centre_id)
    organisation_id = centre.parent_id
    assert organisation_id is not None
    course = await db.get(Course, batch.course_id)
    if course is None:  # unreachable: the foreign key cascades; kept for the type
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    await _require_may_deliver(db, organisation_id, course)
    _refuse_unavailable(course)
    if batch.starts_on < today_ist():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The first day has already passed. Change the dates before publishing",
        )
    batch.status = "published"
    batch.published_at = datetime.now(UTC)
    await db.commit()
    await record(
        db,
        "batch_published",
        user_id=actor.id,
        subject_type="tenant",
        subject_id=organisation_id,
        payload={"own": course.tenant_id == organisation_id},
    )
    return await get_batch(db, tenant, batch_id)


async def _tell_interested(db: AsyncSession, batches: Sequence[Batch], reason: str) -> int:
    """Queue the fixed-words notice to every learner with a live interest in these batches.

    Does not commit. The payload names the course and the reason code and links to the course's
    page; nothing about the learner, the centre's address or any free text.
    """
    if not batches:
        return 0
    ids = [b.id for b in batches]
    rows = (
        await db.execute(
            select(CandidateProfile.user_id, Course.title, Course.slug)
            .select_from(BatchInterest)
            .join(CandidateProfile, CandidateProfile.id == BatchInterest.profile_id)
            .join(Batch, Batch.id == BatchInterest.batch_id)
            .join(Course, Course.id == Batch.course_id)
            .where(
                BatchInterest.batch_id.in_(ids),
                BatchInterest.status.in_(LIVE_INTEREST_STATUSES),
            )
        )
    ).all()
    return await enqueue_many(
        db,
        [
            {
                "recipient_kind": "user",
                "recipient_id": user_id,
                "channel": "in_app",
                "template": "batch_cancelled",
                "payload": {"course": title, "reason": reason, "path": f"/courses/{slug}"},
            }
            for user_id, title, slug in rows
        ],
    )


async def _cancel(db: AsyncSession, batches: Sequence[Batch], reason: str) -> None:
    """Cancel these (locked, still cancellable) batches and queue the notice. Does not commit."""
    now = datetime.now(UTC)
    for batch in batches:
        batch.status = "cancelled"
        batch.cancelled_at = now
        batch.cancel_reason = reason
    await db.flush()
    await _tell_interested(db, batches, reason)


async def cancel_batch(
    db: AsyncSession, tenant: Tenant, actor: User, batch_id: uuid.UUID
) -> BatchOut:
    batch = await _locked(db, tenant, batch_id)
    enrolled = await _enrolled_of(db, batch.id)
    now = phases.phase(
        status=batch.status,
        starts_on=batch.starts_on,
        ends_on=batch.ends_on,
        seats=batch.seats,
        enrolled=enrolled,
        today=today_ist(),
    )
    if now not in phases.CANCELLABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A batch that is "
            f"{now} cannot be cancelled: a class in progress is never stopped from under its "
            "learners",
        )
    centre = await db.get(Tenant, batch.centre_id)
    organisation_id = centre.parent_id if centre is not None else None
    await _cancel(db, [batch], "by_organisation")
    await db.commit()
    if organisation_id is not None:
        await record(
            db,
            "batch_cancelled",
            user_id=actor.id,
            subject_type="tenant",
            subject_id=organisation_id,
            payload={"reason": "by_organisation"},
        )
    return await get_batch(db, tenant, batch_id)


# ------------------------------------------------- what the other modules ask of this one


async def cancel_on_arrangement_ended(
    db: AsyncSession, arrangement: CourseDeliveryAuthorisation
) -> None:
    """Registered with `delivery.on_ended`: runs **inside** the revocation's transaction, after the
    arrangement is flushed as ended and before the commit.

    Cancels the partner's drafts and published batches that have not started, for courses of the
    seller that **no other arrangement still covers**; learners are told. A batch that is running
    finishes: stopping a class in progress harms the people in it more than a withdrawn approval
    harms the seller (ADR-103).
    """
    today = today_ist()
    rows = (
        await db.execute(
            select(Batch, Course)
            .join(Course, Course.id == Batch.course_id)
            .join(Tenant, Tenant.id == Batch.centre_id)
            .where(
                Tenant.parent_id == arrangement.partner_id,
                Course.tenant_id == arrangement.provider_id,
                *([Course.id == arrangement.course_id] if arrangement.course_id else []),
                or_(
                    Batch.status == "draft",
                    and_(Batch.status == "published", Batch.starts_on > today),
                ),
            )
            .with_for_update(of=Batch)
        )
    ).all()
    doomed = [
        batch for batch, course in rows if not await authorises(db, arrangement.partner_id, course)
    ]
    await _cancel(db, doomed, "arrangement_ended")


async def tell_before_deleting(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Queue the cancellation notice for learners whose batch goes with a deleted organisation:
    its centres' batches, and the batches of its courses delivered elsewhere. Does not commit and
    deletes nothing: the caller's deletion cascades the rows, and this is the one thing that must
    not be silent."""
    centre_ids = select(Tenant.id).where(Tenant.parent_id == tenant_id)
    own_centre = (
        await db.scalars(
            select(Batch).where(
                Batch.centre_id.in_(centre_ids),
                Batch.status.in_(("draft", "published")),
                Batch.ends_on >= today_ist(),
            )
        )
    ).all()
    of_courses = (
        await db.scalars(
            select(Batch)
            .join(Course, Course.id == Batch.course_id)
            .where(
                Course.tenant_id == tenant_id,
                Batch.status.in_(("draft", "published")),
                Batch.ends_on >= today_ist(),
            )
        )
    ).all()
    sent = await _tell_interested(db, own_centre, "centre_closed")
    seen = {b.id for b in own_centre}
    sent += await _tell_interested(
        db, [b for b in of_courses if b.id not in seen], "course_unavailable"
    )
    return sent
