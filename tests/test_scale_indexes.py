"""Indexes the scale harness showed were missing (Sprint 50, migration 0047).

A test cannot show a 500,000-row scan, so it asserts the two things that matter: the index
is there with the predicate the drain needs, and the drain's own statement chooses it.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.notifications.models import Notification


async def test_the_drain_has_an_index_that_holds_only_what_it_can_send(
    db: AsyncSession,
) -> None:
    definition = await db.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_notifications_pending_email'")
    )
    assert definition is not None, "migration 0047 not applied"
    assert "created_at" in definition
    assert "status" in definition and "pending" in definition
    assert "channel" in definition and "email" in definition


async def test_the_employer_overview_has_its_application_index(db: AsyncSession) -> None:
    definition = await db.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_applications_job_status'")
    )
    assert definition is not None and "job_id, status" in definition


async def test_the_drains_statement_chooses_it_among_a_backlog_of_in_app_rows(
    db: AsyncSession,
) -> None:
    """In-app notices stay `pending` for ever, so they are most of the 'pending' rows. The plan
    for the drain's own query must not be the one that walks them."""
    old = datetime.now(UTC) - timedelta(days=30)
    for n in range(600):
        db.add(
            Notification(
                recipient_kind="user",
                recipient_id=uuid.uuid4(),
                channel="in_app",
                template="job_alert",
                payload={},
                status="pending",
                created_at=old - timedelta(minutes=n),
            )
        )
    for _n in range(20):
        db.add(
            Notification(
                recipient_kind="user",
                recipient_id=uuid.uuid4(),
                channel="email",
                template="job_alert",
                payload={},
                status="pending",
            )
        )
    await db.flush()
    await db.execute(text("ANALYZE notifications"))

    plan = "\n".join(
        row[0]
        for row in await db.execute(
            text(
                "EXPLAIN SELECT * FROM notifications WHERE status = 'pending' "
                "AND channel = 'email' ORDER BY created_at LIMIT 50 FOR UPDATE SKIP LOCKED"
            )
        )
    )
    assert "ix_notifications_pending_email" in plan, plan
