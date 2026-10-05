"""What the outbox keeps, and for how long (Sprint 49).

Nothing ever deleted a notification: an email delivered years ago sat in the table with
its payload for as long as the database existed. The rules worth pinning are the
exceptions -- what must *not* be deleted, however old -- because a retention job that
removes a message still owed, or an offer nobody has seen, is worse than none.
"""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import Settings
from api.modules.notifications import tasks
from api.modules.notifications.models import Notification
from api.modules.notifications.service import purge_expired


def _row(
    *,
    channel: str,
    age_days: int,
    status: str = "pending",
    read: bool = False,
    template: str = "application_received",
) -> Notification:
    created = datetime.now(UTC) - timedelta(days=age_days)
    return Notification(
        recipient_kind="user",
        recipient_id=uuid.uuid4(),
        channel=channel,
        template=template,
        payload={},
        status=status,
        created_at=created,
        read_at=created if read else None,
    )


async def _survivors(db: AsyncSession, rows: dict[str, Notification]) -> set[str]:
    alive = set((await db.scalars(select(Notification.id))).all())
    return {name for name, row in rows.items() if row.id in alive}


async def _seed(db: AsyncSession) -> dict[str, Notification]:
    rows = {
        "sent_old": _row(channel="email", age_days=120, status="sent"),
        "sent_recent": _row(channel="email", age_days=10, status="sent"),
        "skipped_old": _row(channel="email", age_days=120, status="skipped"),
        "failed_old": _row(channel="email", age_days=120, status="failed"),
        "pending_ancient": _row(channel="email", age_days=900, status="pending"),
        "read_old": _row(channel="in_app", age_days=120, read=True, template="vacancy_closed"),
        "read_recent": _row(channel="in_app", age_days=30, read=True, template="vacancy_closed"),
        "unread_old": _row(channel="in_app", age_days=120, template="sponsor_offer"),
        "unread_ancient": _row(channel="in_app", age_days=200, template="sponsor_offer"),
    }
    db.add_all(rows.values())
    await db.flush()
    return rows


class TestRetention:
    async def test_it_removes_exactly_what_is_past_its_retention(self, db: AsyncSession) -> None:
        rows = await _seed(db)

        counts = await purge_expired(db, retention_days=90)

        assert await _survivors(db, rows) == {
            "sent_recent",
            "pending_ancient",
            "read_recent",
            "unread_old",
        }
        assert counts == {"delivered": 3, "read": 1, "unread": 1}

    async def test_a_message_still_owed_is_never_deleted_however_old(
        self, db: AsyncSession
    ) -> None:
        """`pending` is not "old", it is *owed*. The drain will send it or fail it; a
        retention job that got there first would lose a message the person was promised."""
        rows = {"owed": _row(channel="email", age_days=5000, status="pending")}
        db.add_all(rows.values())
        await db.flush()

        await purge_expired(db, retention_days=7)

        assert await _survivors(db, rows) == {"owed"}

    async def test_an_unopened_notice_outlives_an_opened_one(self, db: AsyncSession) -> None:
        """It may be an offer to sponsor a standard that the person has not seen yet
        (ADR-048): kept for twice the period, and gone after it."""
        rows = {
            "opened": _row(channel="in_app", age_days=100, read=True),
            "unopened": _row(channel="in_app", age_days=100),
            "unopened_ancient": _row(channel="in_app", age_days=181),
        }
        db.add_all(rows.values())
        await db.flush()

        await purge_expired(db, retention_days=90)

        assert await _survivors(db, rows) == {"unopened"}

    async def test_it_is_idempotent(self, db: AsyncSession) -> None:
        await _seed(db)
        await purge_expired(db, retention_days=90)
        assert await purge_expired(db, retention_days=90) == {
            "delivered": 0,
            "read": 0,
            "unread": 0,
        }


class TestTheJob:
    async def test_the_task_applies_the_configured_period(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = {
            "forty_days": _row(channel="email", age_days=40, status="sent"),
            "ten_days": _row(channel="email", age_days=10, status="sent"),
        }
        db.add_all(rows.values())
        await db.flush()

        class _Session:
            async def __aenter__(self) -> AsyncSession:
                return db

            async def __aexit__(self, *exc: object) -> bool:
                return False

        monkeypatch.setattr(tasks, "get_sessionmaker", lambda: lambda: _Session())
        monkeypatch.setattr(
            tasks, "get_settings", lambda: SimpleNamespace(notification_retention_days=30)
        )

        removed = await tasks.purge_expired_notifications({})

        assert removed["delivered"] == 1
        assert await _survivors(db, rows) == {"ten_days"}

    def test_the_period_defaults_to_ninety_days_and_has_a_floor_of_a_week(self) -> None:
        assert Settings().notification_retention_days == 90
        with pytest.raises(ValueError):
            Settings(notification_retention_days=6)
