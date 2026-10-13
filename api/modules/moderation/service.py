"""Reports about listings, and an operator's decision about them (Sprint 59, BL-14.4, ADR-069).

Rules, each in one place:

* **Who may report** (`submit_report`): a signed-in person, about a listing that is published (a
  draft is a 404, so its existence is not confirmed), once, and not about their own organisation's.
  A budget bounds how many a person may file in a day.
* **An operator decides about a listing, not a report** (`queue`, `dismiss`, `takedown`): reports
  are grouped by listing, and a decision closes every open report on it together.
* **The takedown itself is marketplace's** (`marketplace.take_down_listing`), because whether a
  listing may go live is an invariant of the listing. This module closes the reports in the same
  transaction and records the event.
* **Nobody is told who reported.** The payload to the organisation, every event and the owner's own
  view carry a reason and a count, never the reporter. Only an operator sees a reporter, masked.

`record()` commits, so every event here is recorded after the business commit and in this layer,
never in a handler.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.redaction import mask_email, mask_phone
from api.core.security import enforce_budget
from api.modules.analytics import record
from api.modules.identity.models import Membership, Tenant, User
from api.modules.marketplace import (
    Course,
    Job,
    get_course_by_slug,
    get_job_by_slug,
    restore_listing,
    take_down_listing,
)
from api.modules.moderation.models import CLOSED, ListingReport
from api.modules.moderation.schemas import (
    ListingReportsOut,
    OrganisationRefOut,
    ReporterOut,
    ReportIn,
    ReportOut,
    ReportQueueOut,
    TargetType,
)

log = structlog.get_logger("iism.moderation")

_SHOWN_PER_LISTING = 10


def _model(target_type: str) -> type[Job] | type[Course]:
    return Job if target_type == "job" else Course


async def submit_report(
    db: AsyncSession, user: User, target_type: TargetType, slug: str, payload: ReportIn
) -> None:
    listing = (
        await get_job_by_slug(db, slug)
        if target_type == "job"
        else await get_course_by_slug(db, slug)
    )
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")

    # Their own organisation's listing is theirs to unpublish, not to report.
    own = await db.scalar(
        select(Membership.id).where(
            Membership.user_id == user.id, Membership.tenant_id == listing.tenant_id
        )
    )
    if own is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You manage this listing. You can unpublish it yourself."
        )

    await enforce_budget(
        "listing-report",
        f"user:{user.id}",
        limit=_per_day(),
        window_seconds=86_400,
        noun="reports",
    )

    report = ListingReport(
        target_type=target_type,
        target_id=listing.id,
        target_slug=listing.slug,
        target_title=listing.title,
        tenant_id=listing.tenant_id,
        reporter_id=user.id,
        reason=payload.reason,
        detail=payload.detail,
    )
    # The unique constraint is the arbiter, not a read beforehand: two taps are two requests.
    try:
        async with db.begin_nested():
            db.add(report)
    except IntegrityError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You have already reported this listing."
        ) from error
    await db.commit()
    log.info("moderation.reported", target_type=target_type, reason=payload.reason)
    await record(
        db,
        "listing_reported",
        user_id=user.id,
        subject_type=target_type,
        subject_id=listing.id,
        payload={"reason": payload.reason},
    )


def _per_day() -> int:
    from api.core.config import get_settings

    return get_settings().report_submissions_per_day


async def queue(db: AsyncSession, *, view: str, limit: int) -> ReportQueueOut:
    open_listings = (
        await db.scalar(
            select(func.count()).select_from(
                select(ListingReport.target_type, ListingReport.target_id)
                .where(ListingReport.status == "open")
                .group_by(ListingReport.target_type, ListingReport.target_id)
                .subquery()
            )
        )
    ) or 0
    taken_down = 0
    for model in (Job, Course):
        taken_down += (
            await db.scalar(
                select(func.count()).select_from(model).where(model.taken_down_at.is_not(None))
            )
            or 0
        )

    items = await _open_groups(db, limit) if view == "open" else await _taken_down_groups(db, limit)
    return ReportQueueOut(items=items, open_listings=open_listings, taken_down=taken_down)


def _group(
    target_type: str,
    listing: Job | Course,
    tenant: Tenant | None,
    reports: list[tuple[ListingReport, User | None]],
) -> ListingReportsOut:
    reasons: dict[str, int] = {}
    for report, _ in reports:
        reasons[report.reason] = reasons.get(report.reason, 0) + 1
    return ListingReportsOut(
        target_type=cast(TargetType, target_type),
        target_id=listing.id,
        slug=listing.slug,
        title=listing.title,
        organisation=OrganisationRefOut(slug=tenant.slug, name=tenant.name) if tenant else None,
        status=listing.status,
        open_reports=len(reports),
        reasons=reasons,
        oldest=min((r.created_at for r, _ in reports), default=None),
        reports=[
            ReportOut(
                reason=r.reason,
                detail=r.detail,
                reporter=ReporterOut(
                    phone=mask_phone(u.phone) if u and u.phone else None,
                    email=mask_email(u.email) if u and u.email else None,
                ),
                created_at=r.created_at,
            )
            for r, u in reports[:_SHOWN_PER_LISTING]
        ],
        taken_down_at=listing.taken_down_at,
        takedown_reason=listing.takedown_reason,
    )


async def _open_groups(db: AsyncSession, limit: int) -> list[ListingReportsOut]:
    """Most distinct reporters first, then the oldest: the listing most people have flagged for
    longest. One reporter is one report (the unique constraint), so the count is the headcount."""
    groups = (
        await db.execute(
            select(ListingReport.target_type, ListingReport.target_id)
            .where(ListingReport.status == "open")
            .group_by(ListingReport.target_type, ListingReport.target_id)
            .order_by(func.count().desc(), func.min(ListingReport.created_at))
            .limit(limit)
        )
    ).all()
    out: list[ListingReportsOut] = []
    for target_type, target_id in groups:
        model = _model(target_type)
        listing = cast(Job | Course | None, await db.get(model, target_id))
        rows = (
            await db.execute(
                select(ListingReport, User)
                .join(User, User.id == ListingReport.reporter_id)
                .where(
                    ListingReport.status == "open",
                    ListingReport.target_type == target_type,
                    ListingReport.target_id == target_id,
                )
                .order_by(ListingReport.created_at)
            )
        ).all()
        if listing is None:
            continue  # deleted since; the purge removes the rows
        tenant = await db.get(Tenant, listing.tenant_id)
        out.append(_group(target_type, listing, tenant, [(r, u) for r, u in rows]))
    return out


async def _taken_down_groups(db: AsyncSession, limit: int) -> list[ListingReportsOut]:
    out: list[ListingReportsOut] = []
    for target_type, model in (("job", Job), ("course", Course)):
        rows = await db.scalars(
            select(model)
            .where(model.taken_down_at.is_not(None))
            .order_by(model.taken_down_at.desc())
            .limit(limit)
        )
        for found in rows.all():
            listing = cast(Job | Course, found)
            out.append(_group(target_type, listing, await db.get(Tenant, listing.tenant_id), []))
    out.sort(key=lambda g: g.taken_down_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    return out[:limit]


async def _lock_open(
    db: AsyncSession, target_type: str, target_id: uuid.UUID
) -> list[ListingReport]:
    rows = await db.scalars(
        select(ListingReport)
        .where(
            ListingReport.status == "open",
            ListingReport.target_type == target_type,
            ListingReport.target_id == target_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


def _close(reports: list[ListingReport], outcome: str, actor: User) -> None:
    now = datetime.now(UTC)
    for r in reports:
        r.status = outcome
        r.handled_by = actor.id
        r.handled_at = now


async def dismiss(
    db: AsyncSession, target_type: TargetType, target_id: uuid.UUID, *, actor: User
) -> int:
    reports = await _lock_open(db, target_type, target_id)
    if not reports:
        raise HTTPException(status.HTTP_409_CONFLICT, "There are no open reports on this listing.")
    _close(reports, "dismissed", actor)
    await db.commit()
    await record(
        db,
        "listing_reports_dismissed",
        user_id=actor.id,
        subject_type=target_type,
        subject_id=target_id,
        payload={"reports": len(reports)},
    )
    return len(reports)


async def takedown(
    db: AsyncSession, target_type: TargetType, target_id: uuid.UUID, reason: str, *, actor: User
) -> int:
    """Close the open reports and remove the listing in **one transaction**: `take_down_listing`
    commits, and a refusal (already taken down) rolls the report changes back with it."""
    reports = await _lock_open(db, target_type, target_id)
    _close(reports, "actioned", actor)
    await take_down_listing(db, target_type, target_id, reason)
    log.warning("moderation.taken_down", target_type=target_type, reports=len(reports))
    await record(
        db,
        "listing_taken_down",
        user_id=actor.id,
        subject_type=target_type,
        subject_id=target_id,
        payload={"reports": len(reports), "reasons": sorted({r.reason for r in reports})},
    )
    return len(reports)


async def restore(
    db: AsyncSession, target_type: TargetType, target_id: uuid.UUID, *, actor: User
) -> None:
    await restore_listing(db, target_type, target_id)
    log.warning("moderation.restored", target_type=target_type)
    await record(
        db,
        "listing_restored",
        user_id=actor.id,
        subject_type=target_type,
        subject_id=target_id,
        payload=None,
    )


# ------------------------------------------------------ retention and the person's rights


async def purge_expired(db: AsyncSession, *, retention_days: int) -> int:
    """Delete a closed report a year after it was closed, and any report whose listing no longer
    exists. An open report on a live listing is never deleted, however old.

    The second rule is why `target_id` is not a foreign key and why no writer of a deleted listing
    had to learn about reports: a listing the owner deleted, or an organisation erased with its
    listings, leaves rows this finds on its own.
    """
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    closed = await db.execute(
        delete(ListingReport).where(
            ListingReport.status.in_(CLOSED), ListingReport.handled_at < cutoff
        )
    )
    orphaned = await db.execute(
        delete(ListingReport).where(
            ListingReport.target_type == "job",
            ~exists().where(Job.id == ListingReport.target_id),
        )
    )
    orphaned_courses = await db.execute(
        delete(ListingReport).where(
            ListingReport.target_type == "course",
            ~exists().where(Course.id == ListingReport.target_id),
        )
    )
    await db.commit()
    return sum(int(getattr(r, "rowcount", 0) or 0) for r in (closed, orphaned, orphaned_courses))


async def export_for_user(db: AsyncSession, user: User) -> list[dict[str, object]]:
    """A person's own reports. Not the outcome, and never an operator's words: what they wrote and
    about what."""
    rows = await db.scalars(
        select(ListingReport)
        .where(ListingReport.reporter_id == user.id)
        .order_by(ListingReport.created_at)
    )
    return [
        {
            "about": r.target_title,
            "kind": r.target_type,
            "reason": r.reason,
            "detail": r.detail,
            "reported_at": r.created_at.isoformat(),
        }
        for r in rows.all()
    ]


async def erase_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(delete(ListingReport).where(ListingReport.reporter_id == user_id))
    # A report a person filed is theirs; one an operator handled keeps `handled_by` as SET NULL.
    await db.execute(
        update(ListingReport).where(ListingReport.handled_by == user_id).values(handled_by=None)
    )
