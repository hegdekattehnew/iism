"""Delivering somebody else's course: asking, inviting, approving, ending (Sprint 97, BL-18.15).

One module owns the rules, each in one place:

* **Only the course's seller approves.** A partner asks (`request_delivery`) or a seller invites
  (`invite_partner`); an invitation is created approved, because the seller's own invitation is its
  approval and the partner is owed no say in an obligation nothing creates until a batch exists.
* **Either side ends it.** `decline` closes a request nobody has approved (the seller refusing, or
  the partner withdrawing); `revoke` ends one that was approved. Nobody else can: a party is the
  seller or the partner of the row, and anybody else gets the 404 of a row that does not exist.
* **Every change locks the row, then re-reads it**: "is it still a request?" is only true while
  nobody is deciding it, so an approve and a withdraw at the same instant cannot both succeed.
  Creation has no row to lock yet, so the partial unique indexes are the arbiter and the loser gets
  the answer it would have got a moment later (409), never a 500 (ADR-052).
* **The other side is told once, in fixed words, through the outbox**, in the act's own transaction
  (an arrangement changed with nobody told is the failure mode, not an unsent mail).
* **`authorises` is the question batches will ask** (Sprint 98): may this organisation deliver this
  course? Own course: yes, with no row. Anybody else's: an approved, unended row that covers it.
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import record
from api.modules.delivery.models import CourseDeliveryAuthorisation as Authorisation
from api.modules.delivery.schemas import (
    AuthorisationOut,
    CourseRefOut,
    DeliveredCourseOut,
    DeliveredOut,
    DeliveryOut,
    OrgRefOut,
    TrainingOrganisationList,
)
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import Course
from api.modules.notifications import enqueue

log = structlog.get_logger("iism.delivery")

# Arrangements an organisation has started and nobody has answered. A cap that deters a script
# writing to a hundred organisations; advisory, like the other abuse caps (ADR-052).
MAX_OPEN_REQUESTS = 20
# The same pair, asking again and again: each ask is a mail to the other side.
MAX_ASKS_PER_PAIR_PER_DAY = 3


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _org_ref(tenant: Tenant) -> OrgRefOut:
    return OrgRefOut(
        slug=tenant.slug, name=tenant.name, city=tenant.city, is_verified=tenant.is_verified
    )


def _not_found() -> HTTPException:
    # One body for a slug that does not exist and one that is not the kind asked for: a caller
    # cannot use this to learn which organisations exist or what they do (ADR-038).
    return HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")


async def _counterpart(db: AsyncSession, slug: str, *, me: Tenant, seller: bool) -> Tenant:
    """The other organisation: a training organisation, not this one, that sells (or delivers)."""
    flag = Tenant.publishes_courses if seller else Tenant.delivers_training
    other = await db.scalar(
        select(Tenant).where(
            Tenant.slug == slug,
            Tenant.tenant_type == "course_provider",
            flag.is_(True),
            Tenant.id != me.id,
        )
    )
    if other is None:
        raise _not_found()
    return other


async def _course_of(db: AsyncSession, provider: Tenant, course_slug: str | None) -> Course | None:
    if course_slug is None:
        return None
    course = await db.scalar(
        select(Course).where(Course.slug == course_slug, Course.tenant_id == provider.id)
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return course


async def authorises(db: AsyncSession, partner_id: uuid.UUID, course: Course) -> bool:
    """May this organisation deliver this course? **The one answer batches will ask.**

    Its own course: always, and no row exists. Somebody else's: only through an approved,
    unended authorisation that names the course or all of the seller's courses.
    """
    if course.tenant_id == partner_id:
        return True
    held = await db.scalar(
        select(Authorisation.id).where(
            Authorisation.partner_id == partner_id,
            Authorisation.provider_id == course.tenant_id,
            or_(Authorisation.course_id.is_(None), Authorisation.course_id == course.id),
            Authorisation.approved_at.is_not(None),
            Authorisation.ended_at.is_(None),
        )
    )
    return held is not None


async def _lock_parties(db: AsyncSession, provider_id: uuid.UUID, partner_id: uuid.UUID) -> None:
    """Share-lock both organisations and read what each does again, under the lock.

    `require()` asked "does this organisation deliver?" when the request arrived; an owner turning
    *delivers training* (or *sells courses*) off takes the ownership lock (`FOR NO KEY UPDATE`) and
    counts the arrangements. `FOR SHARE` conflicts with it, so an arrangement made at the same
    instant either lands before the count (the owner is refused) or finds the flag off and is itself
    refused: never an arrangement under an organisation that no longer does the thing. Ascending
    id, the one order that cannot deadlock.
    """
    flags = {
        row.id: row
        for row in (
            await db.execute(
                select(Tenant.id, Tenant.publishes_courses, Tenant.delivers_training)
                .where(Tenant.id.in_([provider_id, partner_id]))
                .order_by(Tenant.id)
                .with_for_update(read=True)
                .execution_options(populate_existing=True)
            )
        ).all()
    }
    provider, partner = flags.get(provider_id), flags.get(partner_id)
    if (
        provider is None
        or partner is None
        or not provider.publishes_courses
        or not partner.delivers_training
    ):
        raise _not_found()


async def _create(
    db: AsyncSession,
    *,
    provider: Tenant,
    partner: Tenant,
    course: Course | None,
    initiated_by: str,
    actor: User,
    template: str,
    event: str,
) -> Authorisation:
    now = datetime.now(UTC)
    # Capture before any rollback below expires the instances (Sprint 55's lesson).
    provider_id, partner_id = provider.id, partner.id
    await _lock_parties(db, provider_id, partner_id)
    other = partner if initiated_by == "provider" else provider
    me = provider if initiated_by == "provider" else partner
    other_slug, me_name, me_id = other.slug, me.name, me.id

    open_rows = (
        await db.scalars(
            select(Authorisation).where(
                Authorisation.provider_id == provider_id,
                Authorisation.partner_id == partner_id,
                Authorisation.ended_at.is_(None),
            )
        )
    ).all()
    # The same scope already open: said before any cap, because "try again tomorrow" is the wrong
    # answer to a double tap. The unique indexes below remain the arbiter when two taps race.
    if any(r.course_id == (course.id if course is not None else None) for r in open_rows):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "There is already an open arrangement for that"
        )
    if course is not None and any(r.course_id is None for r in open_rows):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "All of that organisation's courses are already covered by an arrangement",
        )

    recent = (
        await db.scalar(
            select(func.count())
            .select_from(Authorisation)
            .where(
                Authorisation.provider_id == provider_id,
                Authorisation.partner_id == partner_id,
                Authorisation.requested_at >= now - timedelta(days=1),
            )
        )
    ) or 0
    if recent >= MAX_ASKS_PER_PAIR_PER_DAY:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "There have been several requests between these two organisations today. "
            "Try again tomorrow",
            headers={"retry-after": "3600"},
        )
    open_by_me = (
        await db.scalar(
            select(func.count())
            .select_from(Authorisation)
            .where(
                Authorisation.initiated_by == initiated_by,
                (
                    Authorisation.provider_id
                    if initiated_by == "provider"
                    else Authorisation.partner_id
                )
                == me_id,
                Authorisation.ended_at.is_(None),
                Authorisation.approved_at.is_(None),
            )
        )
    ) or 0
    if open_by_me >= MAX_OPEN_REQUESTS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You have {MAX_OPEN_REQUESTS} requests waiting for an answer. "
            "Wait for some to be answered",
        )

    row = Authorisation(
        provider_id=provider_id,
        partner_id=partner_id,
        course_id=course.id if course is not None else None,
        initiated_by=initiated_by,
        requested_at=now,
        requested_by=actor.id,
        # A seller's invitation is its approval.
        approved_at=now if initiated_by == "provider" else None,
        approved_by=actor.id if initiated_by == "provider" else None,
    )
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError as error:
        # The unique indexes are the arbiter of a double tap: the other request got there first.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "There is already an open arrangement for that"
        ) from error
    await enqueue(
        db,
        recipient_kind="tenant",
        recipient_id=other.id,
        channel="email",
        template=template,
        payload={"organisation": me_name, "path": f"/employer/{other_slug}/delivery"},
    )
    await db.commit()
    await db.refresh(row)
    await record(
        db,
        event,
        user_id=actor.id,
        subject_type="tenant",
        subject_id=me_id,
        payload={"all_courses": course is None},
    )
    return row


async def request_delivery(
    db: AsyncSession,
    *,
    partner: Tenant,
    actor: User,
    provider_slug: str,
    course_slug: str | None,
) -> Authorisation:
    """A delivering organisation asks a seller to let it deliver one course, or all of them."""
    provider = await _counterpart(db, provider_slug, me=partner, seller=True)
    course = await _course_of(db, provider, course_slug)
    return await _create(
        db,
        provider=provider,
        partner=partner,
        course=course,
        initiated_by="partner",
        actor=actor,
        template="delivery_requested",
        event="delivery_requested",
    )


async def invite_partner(
    db: AsyncSession,
    *,
    provider: Tenant,
    actor: User,
    partner_slug: str,
    course_slug: str | None,
) -> Authorisation:
    """A seller authorises a delivering organisation: created approved, and the partner is told."""
    partner = await _counterpart(db, partner_slug, me=provider, seller=False)
    course = await _course_of(db, provider, course_slug)
    return await _create(
        db,
        provider=provider,
        partner=partner,
        course=course,
        initiated_by="provider",
        actor=actor,
        template="delivery_invited",
        event="delivery_invited",
    )


async def _locked(db: AsyncSession, org: Tenant, authorisation_id: uuid.UUID) -> Authorisation:
    """The row, locked and re-read, if this organisation is a party to it (else the 404 of none)."""
    row = await db.scalar(
        select(Authorisation)
        .where(
            Authorisation.id == authorisation_id,
            or_(Authorisation.provider_id == org.id, Authorisation.partner_id == org.id),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arrangement not found")
    return row


def _side_of(org: Tenant, row: Authorisation) -> str:
    return "provider" if row.provider_id == org.id else "partner"


async def _notify_other(db: AsyncSession, org: Tenant, row: Authorisation, template: str) -> None:
    other_id = row.partner_id if row.provider_id == org.id else row.provider_id
    other = await db.get(Tenant, other_id)
    if other is None:  # the organisation was erased meanwhile: nobody to tell
        return
    await enqueue(
        db,
        recipient_kind="tenant",
        recipient_id=other.id,
        channel="email",
        template=template,
        payload={"organisation": org.name, "path": f"/employer/{other.slug}/delivery"},
    )


async def approve(
    db: AsyncSession, *, provider: Tenant, actor: User, authorisation_id: uuid.UUID
) -> Authorisation:
    """The seller says yes to a partner's request."""
    row = await _locked(db, provider, authorisation_id)
    if row.provider_id != provider.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the organisation that sells the course can approve"
        )
    if row.state != "requested":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This request is already {row.state}")
    row.approved_at = datetime.now(UTC)
    row.approved_by = actor.id
    await _notify_other(db, provider, row, "delivery_approved")
    provider_id = provider.id
    await db.commit()
    await db.refresh(row)
    await record(
        db,
        "delivery_approved",
        user_id=actor.id,
        subject_type="tenant",
        subject_id=provider_id,
        payload={"all_courses": row.course_id is None},
    )
    return row


async def _end(
    db: AsyncSession,
    *,
    org: Tenant,
    actor: User,
    authorisation_id: uuid.UUID,
    from_state: str,
    template: str,
    how: str,
) -> Authorisation:
    row = await _locked(db, org, authorisation_id)
    if row.state != from_state:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This arrangement is already {row.state}")
    side = _side_of(org, row)
    row.ended_at = datetime.now(UTC)
    row.ended_by_side = side
    row.ended_by = actor.id
    await _notify_other(db, org, row, template)
    org_id = org.id
    await db.commit()
    await db.refresh(row)
    await record(
        db,
        "delivery_ended",
        user_id=actor.id,
        subject_type="tenant",
        subject_id=org_id,
        payload={"how": how, "side": side},
    )
    return row


async def decline(
    db: AsyncSession, *, org: Tenant, actor: User, authorisation_id: uuid.UUID
) -> Authorisation:
    """Close a request nobody has approved: the seller refusing it, or the partner withdrawing."""
    return await _end(
        db,
        org=org,
        actor=actor,
        authorisation_id=authorisation_id,
        from_state="requested",
        template="delivery_declined",
        how="declined",
    )


async def revoke(
    db: AsyncSession, *, org: Tenant, actor: User, authorisation_id: uuid.UUID
) -> Authorisation:
    """End an approved arrangement. Either side may. Batches (Sprint 98) hang their effects here."""
    return await _end(
        db,
        org=org,
        actor=actor,
        authorisation_id=authorisation_id,
        from_state="approved",
        template="delivery_revoked",
        how="revoked",
    )


# -------------------------------------------------------------------- reading


def _out(
    row: Authorisation,
    *,
    side: str,
    tenants: dict[uuid.UUID, Tenant],
    courses: dict[uuid.UUID, Course],
) -> AuthorisationOut:
    other = tenants[row.provider_id if side == "partner" else row.partner_id]
    course = courses.get(row.course_id) if row.course_id is not None else None
    return AuthorisationOut(
        id=row.id,
        state=row.state,
        side=side,
        initiated_by=row.initiated_by,
        other=_org_ref(other),
        course=CourseRefOut(slug=course.slug, title=course.title) if course is not None else None,
        requested_at=row.requested_at,
        approved_at=row.approved_at,
        ended_at=row.ended_at,
        ended_by_side=row.ended_by_side,
    )


async def _context_rows(
    db: AsyncSession, rows: list[Authorisation]
) -> tuple[dict[uuid.UUID, Tenant], dict[uuid.UUID, Course]]:
    tenant_ids = {r.provider_id for r in rows} | {r.partner_id for r in rows}
    course_ids = {r.course_id for r in rows if r.course_id is not None}
    tenants = (
        {t.id: t for t in (await db.scalars(select(Tenant).where(Tenant.id.in_(tenant_ids)))).all()}
        if tenant_ids
        else {}
    )
    courses = (
        {c.id: c for c in (await db.scalars(select(Course).where(Course.id.in_(course_ids)))).all()}
        if course_ids
        else {}
    )
    return tenants, courses


async def arrangements_of(db: AsyncSession, org: Tenant) -> DeliveryOut:
    """Every arrangement this organisation is in. Open ones first, then the newest."""
    rows = list(
        (
            await db.scalars(
                select(Authorisation)
                .where(or_(Authorisation.provider_id == org.id, Authorisation.partner_id == org.id))
                .order_by(
                    Authorisation.ended_at.is_(None).desc(), Authorisation.requested_at.desc()
                )
            )
        ).all()
    )
    tenants, courses = await _context_rows(db, rows)
    return DeliveryOut(
        as_partner=[
            _out(r, side="partner", tenants=tenants, courses=courses)
            for r in rows
            if r.partner_id == org.id
        ],
        as_provider=[
            _out(r, side="provider", tenants=tenants, courses=courses)
            for r in rows
            if r.provider_id == org.id
        ],
    )


async def search_organisations(
    db: AsyncSession, *, q: str | None, sells: bool, delivers: bool, limit: int
) -> TrainingOrganisationList:
    """Public: training organisations by name, slug or city, narrowed to those that sell or deliver.

    The same facts the public provider page shows: nothing is disclosed that is not public already.
    """
    where = [Tenant.tenant_type == "course_provider"]
    if sells:
        where.append(Tenant.publishes_courses.is_(True))
    if delivers:
        where.append(Tenant.delivers_training.is_(True))
    words = (q or "").strip()
    if words:
        pattern = f"%{_like_escape(words)}%"
        where.append(
            Tenant.name.ilike(pattern, escape="\\")
            | Tenant.slug.ilike(pattern, escape="\\")
            | Tenant.city.ilike(pattern, escape="\\")
        )
    total = (await db.scalar(select(func.count()).select_from(Tenant).where(*where))) or 0
    rows = (
        await db.scalars(
            select(Tenant).where(*where).order_by(func.lower(Tenant.name), Tenant.id).limit(limit)
        )
    ).all()
    return TrainingOrganisationList(items=[_org_ref(t) for t in rows], total=total)


async def authorised_to_deliver(db: AsyncSession, slug: str) -> DeliveredOut | None:
    """What an organisation is **authorised** to deliver for others (public). `None`: no such page.

    Only approved, unended arrangements: a request nobody has answered is not a fact about anybody.
    """
    partner = await db.scalar(
        select(Tenant).where(Tenant.slug == slug, Tenant.tenant_type == "course_provider")
    )
    if partner is None:
        return None
    rows = list(
        (
            await db.scalars(
                select(Authorisation)
                .where(
                    Authorisation.partner_id == partner.id,
                    Authorisation.approved_at.is_not(None),
                    Authorisation.ended_at.is_(None),
                )
                .order_by(Authorisation.approved_at.desc())
            )
        ).all()
    )
    tenants, courses = await _context_rows(db, rows)
    return DeliveredOut(
        items=[
            DeliveredCourseOut(
                provider=_org_ref(tenants[r.provider_id]),
                course=(
                    CourseRefOut(slug=courses[r.course_id].slug, title=courses[r.course_id].title)
                    if r.course_id is not None and r.course_id in courses
                    else None
                ),
            )
            for r in rows
        ]
    )
