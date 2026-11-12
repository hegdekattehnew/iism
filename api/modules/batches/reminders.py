"""Telling a learner a batch they asked about starts soon (Sprint 101, ADR-103, BL-20.4).

Runs in the **worker**, never in a request. For every published batch that starts within
`REMIND_WITHIN_DAYS` and has not been announced, it stamps `start_notice_at` **first** and commits,
then queues one in-app notice to each learner with a live interest. Under-telling is recoverable by
hand and telling twice is not (the alert sweep's rule), so a crash between the two costs the rest of
that batch's reminders and never repeats one.

**Only learners who registered are written to.** A learner who never asked is not told about a batch
"near them": that is an unsolicited message, which `alerts/` owns (the opt-out and the daily cap),
and it is deliberately not built here. The notice names the course and the centre and says whether
the learner holds a seat; it carries nothing about anybody else, and a push says only fixed words.
"""

import uuid
from datetime import date, timedelta

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.core.clock import today_ist
from api.modules.batches.models import LIVE_INTEREST_STATUSES, TAKEN_STATUSES, Batch, BatchInterest
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, Course
from api.modules.notifications import enqueue_many

log = structlog.get_logger("iism.batches")

REMIND_WITHIN_DAYS = 3
SWEEP_LIMIT = 100


async def claim_starting(db: AsyncSession, today: date) -> list[uuid.UUID]:
    """Stamp and return the batches to announce, oldest start first. Commits."""
    ids = list(
        (
            await db.scalars(
                select(Batch.id)
                .where(
                    Batch.status == "published",
                    Batch.start_notice_at.is_(None),
                    Batch.starts_on >= today,
                    Batch.starts_on <= today + timedelta(days=REMIND_WITHIN_DAYS),
                )
                .order_by(Batch.starts_on, Batch.id)
                .limit(SWEEP_LIMIT)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    if ids:
        await db.execute(update(Batch).where(Batch.id.in_(ids)).values(start_notice_at=func.now()))
    await db.commit()
    return ids


async def tell_starting(db: AsyncSession, batch_ids: list[uuid.UUID]) -> int:
    """Queue the notice to every learner with a live interest in these batches. Commits."""
    if not batch_ids:
        return 0
    centre = aliased(Tenant)
    rows = (
        await db.execute(
            select(
                CandidateProfile.user_id,
                User.preferred_locale,
                BatchInterest.status,
                Course.title,
                centre.name,
                Batch.id,
                Batch.starts_on,
            )
            .select_from(BatchInterest)
            .join(CandidateProfile, CandidateProfile.id == BatchInterest.profile_id)
            .join(User, User.id == CandidateProfile.user_id)
            .join(Batch, Batch.id == BatchInterest.batch_id)
            .join(Course, Course.id == Batch.course_id)
            .join(centre, centre.id == Batch.centre_id)
            .where(
                BatchInterest.batch_id.in_(batch_ids),
                BatchInterest.status.in_(LIVE_INTEREST_STATUSES),
            )
        )
    ).all()
    sent = await enqueue_many(
        db,
        [
            {
                "recipient_kind": "user",
                "recipient_id": user_id,
                "channel": "in_app",
                "template": "batch_starting",
                "locale": locale or "en",
                "payload": {
                    "course": title,
                    "centre": centre_name,
                    "starts_on": starts_on.isoformat(),
                    # Whether they hold a seat: the words differ, never the rest of the notice.
                    "enrolled": status in TAKEN_STATUSES,
                    "path": f"/batches/{batch_id}",
                },
            }
            for user_id, locale, status, title, centre_name, batch_id, starts_on in rows
        ],
    )
    await db.commit()
    return sent


async def sweep(db: AsyncSession, today: date | None = None) -> dict[str, int]:
    ids = await claim_starting(db, today or today_ist())
    sent = await tell_starting(db, ids)
    if ids:
        log.info("batches.reminders_sent", batches=len(ids), notices=sent)
    return {"batches": len(ids), "notices": sent}
