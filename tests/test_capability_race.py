"""Sprint 94, ADR-102: two owners changing what an organisation does at once.

An organisation must always sell courses, deliver training, or both. The guard that says so reads
the two flags and the write that follows changes one of them, with nothing between: under READ
COMMITTED owner A turning off *sells courses* and owner B turning off *delivers training* each read
"both are on" and each pass, and the organisation ends up doing **nothing**. That is the shape of
Sprint 44's last-owner race one table over, and it needs the same answer: the tenant row is locked
first and the flags are read again under the lock.

Real concurrency, so committed rows through the service's own sessionmaker (the suite's `db`
fixture is one connection in one rolled-back transaction and cannot show a race), and the window is
widened on purpose so the interleaving does not depend on scheduler timing.
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
from api.modules.identity import capabilities
from api.modules.identity.models import Membership, Tenant, User


@dataclass
class Org:
    tenant_id: uuid.UUID
    owners: list[uuid.UUID]


async def _make_org() -> Org:
    suffix = uuid.uuid4().hex[:10]
    async with get_sessionmaker()() as db:
        tenant = Tenant(
            slug=f"cap-{suffix}",
            name=f"Capability Fixtures {suffix}",
            tenant_type="course_provider",
            publishes_courses=True,
            delivers_training=True,
        )
        db.add(tenant)
        await db.flush()
        users = [
            User(email=f"cap-{suffix}-{i}@iism-fixtures.co.in", full_name=f"Owner {i}")
            for i in range(2)
        ]
        db.add_all(users)
        await db.flush()
        for user in users:
            db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
        await db.commit()
        return Org(tenant.id, [u.id for u in users])


async def _erase(org: Org) -> None:
    async with get_sessionmaker()() as db:
        await db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.subject_id == org.tenant_id))
        await db.execute(delete(Membership).where(Membership.tenant_id == org.tenant_id))
        await db.execute(delete(Tenant).where(Tenant.id == org.tenant_id))
        await db.execute(delete(User).where(User.id.in_(org.owners)))
        await db.commit()


@pytest.fixture
async def org() -> AsyncIterator[Org]:
    made = await _make_org()
    try:
        yield made
    finally:
        await _erase(made)


@pytest.fixture
def _slow_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold each guard open for a moment after it has answered, inside whatever protects it."""
    published = capabilities._published_courses
    delivering = capabilities.delivery_in_progress

    async def slow_published(db, tenant):  # type: ignore[no-untyped-def]
        answer = await published(db, tenant)
        await asyncio.sleep(0.4)
        return answer

    async def slow_delivering(db, tenant):  # type: ignore[no-untyped-def]
        answer = await delivering(db, tenant)
        await asyncio.sleep(0.4)
        return answer

    monkeypatch.setattr(capabilities, "_published_courses", slow_published)
    monkeypatch.setattr(capabilities, "delivery_in_progress", slow_delivering)


async def _change(org: Org, actor_index: int, **flags: bool) -> int:
    async with get_sessionmaker()() as db:
        tenant = await db.get(Tenant, org.tenant_id)
        actor = await db.get(User, org.owners[actor_index])
        assert tenant is not None and actor is not None
        try:
            await capabilities.set_capabilities(db, tenant=tenant, actor=actor, **flags)
        except HTTPException as refusal:
            return refusal.status_code
        return 200


async def _flags(org: Org) -> tuple[bool, bool]:
    async with get_sessionmaker()() as db:
        row = (
            await db.execute(
                select(Tenant.publishes_courses, Tenant.delivers_training).where(
                    Tenant.id == org.tenant_id
                )
            )
        ).one()
        return row[0], row[1]


@pytest.fixture
def _no_membership_reread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take away the other thing that happens to refresh the tenant.

    `_require_owner_now` re-reads the caller's membership with `populate_existing`, and
    `Membership.tenant` is a `selectin` load, so the tenant is refreshed as a side effect. That
    is not something to lean on: `set_capabilities` re-reads the flags itself, and with this
    patch it is the only thing that can.
    """

    async def nothing(db, tenant_id, user_id):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(capabilities, "_require_owner_now", nothing)


class TestTwoOwnersAtOnce:
    async def test_the_organisation_is_never_left_doing_nothing(
        self, org: Org, _slow_guards: None
    ) -> None:
        results = await asyncio.gather(
            _change(org, 0, sells_courses=False), _change(org, 1, delivers_training=False)
        )
        assert sorted(results) == [200, 409], "one wins and the other is told it would do nothing"
        sells, delivers = await _flags(org)
        assert sells or delivers, "an organisation that neither sells nor delivers can do nothing"

    async def test_two_owners_asking_for_the_same_thing_both_succeed(
        self, org: Org, _slow_guards: None
    ) -> None:
        """The lock serialises; it does not turn a harmless repeat into a refusal."""
        results = await asyncio.gather(
            _change(org, 0, delivers_training=False), _change(org, 1, delivers_training=False)
        )
        assert results == [200, 200]
        assert await _flags(org) == (True, False)
        async with get_sessionmaker()() as db:
            events = (
                await db.scalars(
                    select(AnalyticsEvent).where(
                        AnalyticsEvent.name == "organisation_capability_changed",
                        AnalyticsEvent.subject_id == org.tenant_id,
                    )
                )
            ).all()
        assert len(events) == 1, "the second request found nothing to change and recorded nothing"

    async def test_the_flags_are_read_again_by_the_function_itself(
        self, org: Org, _slow_guards: None, _no_membership_reread: None
    ) -> None:
        results = await asyncio.gather(
            _change(org, 0, sells_courses=False), _change(org, 1, delivers_training=False)
        )
        assert sorted(results) == [200, 409]
        sells, delivers = await _flags(org)
        assert sells or delivers
