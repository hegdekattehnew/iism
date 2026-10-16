"""An operator removes a listing, or puts it back (Sprint 59, BL-14.4, ADR-069).

**Marketplace owns this, not the module that collects the reports.** Whether a listing may go live
is an invariant of the listing, and `moderation/` only decides *that* one should come down. Keeping
the writes here means every writer of "published" can be listed in one place (the convention
Sprint 53 wrote down): `publishing.set_published`, `course_publishing.set_published` (and so
`bulk.publish_many`, which goes through them) and `publishing.reopen_job`, each of which calls
`refuse_while_taken_down`. A vacancy's posted date (Sprint 74, ADR-084) is kept by
`stamp_publication`, called wherever a job's `status` changes: `publishing.set_published` and the
takedown below. `reopen_job` does not call it, because reopening is not a repost.

**Not a status.** A takedown sets `status="draft"` and stamps `taken_down_at`/`takedown_reason`.
`status == "published"` is compared in about thirty-four places (browse, matching, counts, alerts),
so a draft is gone from every one of them without touching any, where a third status would have
had to be added to each and would have stayed visible wherever one was missed.

A vacancy is also **closed** with the reason `taken_down`, so the people waiting on it are told
through the notice a closed vacancy already sends, and it stops being counted as open.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal, cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.marketplace.models import Course, Job

TargetType = Literal["job", "course"]


def refuse_while_taken_down(listing: Job | Course) -> None:
    """409 on any attempt to put a removed listing live. Editing it stays allowed."""
    if listing.taken_down_at is None:
        return
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        f"This listing was removed by our team on {listing.taken_down_at.date().isoformat()}: "
        f"{listing.takedown_reason} It cannot be published until we have restored it. "
        "If you think this is a mistake, please contact the IISM team.",
    )


def stamp_publication(job: Job, published: bool) -> None:
    """Keep `Job.published_at` true to `status` (Sprint 74, ADR-084). Call it where `status` is set.

    Going live from not-live stamps now; going not-live clears it; publishing a vacancy that is
    already live leaves its date alone (saving twice is not a repost). Reopening a closed vacancy
    never comes here: it was published all along.
    """
    if published and job.status != "published":
        job.published_at = datetime.now(UTC)
    elif not published:
        job.published_at = None


async def _locked(db: AsyncSession, target_type: TargetType, target_id: uuid.UUID) -> Job | Course:
    model: type[Job] | type[Course] = Job if target_type == "job" else Course
    # The row lock: two operators acting on one listing must queue, and the second finds it
    # already taken down.
    listing = await db.scalar(
        select(model)
        .where(model.id == target_id)
        .with_for_update(of=model)
        .execution_options(populate_existing=True)
    )
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    return cast(Job | Course, listing)


async def take_down(
    db: AsyncSession, target_type: TargetType, target_id: uuid.UUID, reason: str
) -> Job | Course:
    """Remove a listing from the public and queue the notices. **Commits.**

    The reason is written for the organisation, which is emailed it, and it is the only text that
    leaves with the notice: never who reported, and never a note meant for the operators.
    """
    listing = await _locked(db, target_type, target_id)
    if listing.taken_down_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This listing is already taken down")

    now = datetime.now(UTC)
    if isinstance(listing, Job):
        stamp_publication(listing, False)
    listing.status = "draft"
    listing.taken_down_at = now
    listing.takedown_reason = reason

    if isinstance(listing, Job) and listing.closed_at is None:
        # Function-level: `publishing` is the module that closes a vacancy and tells its
        # applicants, and it imports this one for the guard above.
        from api.modules.marketplace.publishing import _tell_live_applicants

        listing.closed_at = now
        listing.close_reason = "taken_down"
        await _tell_live_applicants(db, listing)

    await _tell_organisation(db, listing, "listing_removed", reason=reason)
    await db.commit()
    return listing


async def restore(db: AsyncSession, target_type: TargetType, target_id: uuid.UUID) -> Job | Course:
    """Lift the stamp. The listing stays a **draft**: nothing goes live by an operator's hand, the
    owner publishes it again themselves. **Commits.**"""
    listing = await _locked(db, target_type, target_id)
    if listing.taken_down_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This listing is not taken down")

    listing.taken_down_at = None
    listing.takedown_reason = None
    if isinstance(listing, Job) and listing.close_reason == "taken_down":
        # Only the closure the takedown made: a vacancy the employer had already filled stays so.
        listing.closed_at = None
        listing.close_reason = None

    await _tell_organisation(db, listing, "listing_restored")
    await db.commit()
    return listing


async def _tell_organisation(
    db: AsyncSession, listing: Job | Course, template: str, *, reason: str | None = None
) -> None:
    from api.modules.notifications import enqueue

    tenant = listing.tenant  # selectin-loaded on both models
    payload: dict[str, str] = {
        "listing": listing.title,
        "path": f"/employer/{tenant.slug}",  # type: ignore[attr-defined]
    }
    if reason is not None:
        payload["reason"] = reason
    await enqueue(
        db,
        recipient_kind="tenant",
        recipient_id=tenant.id,  # type: ignore[attr-defined]
        channel="email",
        template=template,
        payload=payload,
    )
