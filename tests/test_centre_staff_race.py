"""Sprint 96, ADR-102: two admins asking for the last free manager place at once.

The cap on a centre's managers is counted in one statement and the invitation is written in another.
Under READ COMMITTED two admins each count one place free and each write: the centre ends with one
more manager than it may have. Changing who runs a centre takes the ownership lock on the centre's
row *before* the count, so the second admin waits and then counts the first one's invitation.
Real concurrency on committed rows (the suite's `db` fixture is one connection and cannot show it).
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from api.core.database import get_sessionmaker
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import centre_staff
from api.modules.identity.models import Invitation, Membership, Tenant, User
from api.modules.notifications.models import Notification


@dataclass
class Fixture:
    parent: uuid.UUID
    centre: uuid.UUID
    admins: list[uuid.UUID]


@pytest.fixture
async def fx() -> AsyncIterator[Fixture]:
    suffix = uuid.uuid4().hex[:10]
    async with get_sessionmaker()() as db:
        parent = Tenant(
            slug=f"cs-{suffix}",
            name=f"Staff Race {suffix}",
            tenant_type="course_provider",
            publishes_courses=True,
            delivers_training=True,
        )
        db.add(parent)
        await db.flush()
        centre = Tenant(
            slug=f"cs-{suffix}-c",
            name="Race Centre",
            tenant_type="training_centre",
            parent_id=parent.id,
        )
        admins = [
            User(email=f"cs-{suffix}-{i}@iism-fixtures.co.in", full_name=f"Admin {i}")
            for i in range(2)
        ]
        db.add_all([centre, *admins])
        await db.flush()
        for admin in admins:
            db.add(Membership(user_id=admin.id, tenant_id=parent.id, role="admin"))
        await db.commit()
        made = Fixture(parent.id, centre.id, [a.id for a in admins])
    try:
        yield made
    finally:
        async with get_sessionmaker()() as db:
            ids = (
                await db.scalars(select(Invitation.id).where(Invitation.tenant_id == made.centre))
            ).all()
            await db.execute(
                delete(Notification).where(
                    Notification.recipient_kind == "invitation", Notification.recipient_id.in_(ids)
                )
            )
            await db.execute(delete(Invitation).where(Invitation.tenant_id == made.centre))
            await db.execute(
                delete(AnalyticsEvent).where(
                    AnalyticsEvent.subject_id.in_([made.centre, made.parent])
                )
            )
            await db.execute(delete(Membership).where(Membership.tenant_id == made.parent))
            await db.execute(delete(Tenant).where(Tenant.id == made.centre))
            await db.execute(delete(Tenant).where(Tenant.id == made.parent))
            await db.execute(delete(User).where(User.id.in_(made.admins)))
            await db.commit()


@pytest.fixture
def _slow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold the count open for a moment, inside whatever protects it."""
    count = centre_staff._manager_count

    async def slow(db, centre, now):  # type: ignore[no-untyped-def]
        answer = await count(db, centre, now)
        await asyncio.sleep(0.5)
        return answer

    monkeypatch.setattr(centre_staff, "_manager_count", slow)
    monkeypatch.setattr(centre_staff, "MAX_MANAGERS", 1)


async def _invite(fx: Fixture, admin_index: int, address: str) -> int:
    async with get_sessionmaker()() as db:
        parent = await db.get(Tenant, fx.parent)
        centre = await db.get(Tenant, fx.centre)
        actor = await db.get(User, fx.admins[admin_index])
        assert parent is not None and centre is not None and actor is not None
        try:
            await centre_staff.invite_manager(
                db, parent=parent, centre=centre, actor=actor, email=address
            )
        except HTTPException as refusal:
            return refusal.status_code
        return 201


async def test_two_admins_cannot_both_take_the_last_place(fx: Fixture, _slow: None) -> None:
    suffix = uuid.uuid4().hex[:8]
    results = await asyncio.gather(
        _invite(fx, 0, f"one-{suffix}@iism-fixtures.co.in"),
        _invite(fx, 1, f"two-{suffix}@iism-fixtures.co.in"),
    )
    assert sorted(results) == [201, 409], "one gets the place and the other is told there is none"
    async with get_sessionmaker()() as db:
        open_invitations = (
            await db.scalars(select(Invitation).where(Invitation.tenant_id == fx.centre))
        ).all()
    assert len(open_invitations) == 1
