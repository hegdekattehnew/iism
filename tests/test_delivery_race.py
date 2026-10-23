"""Sprint 97, ADR-102: arrangements being made, decided and switched off at the same instant.

Three races, each with a different arbiter, and each shown to fail without it:

* **Two identical requests** (a double tap): no row exists to lock, so the partial unique index
  decides, and the loser is a 409, never a 500.
* **Approve against withdraw**: both read "requested" and both would write. The row is locked
  (`FOR UPDATE`) and re-read, so exactly one wins and the other is told what it now is.
* **A request against the partner switching delivery off**: `FOR SHARE` on the organisations
  conflicts with the capability change's tenant lock, so a request either lands before the count
  (and the owner is refused) or finds the flag off (and is itself refused).

Real concurrency on committed rows (the suite's `db` fixture is one connection and cannot show it),
with the window widened on purpose so the interleaving does not depend on scheduler timing.
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
from api.modules.delivery import CourseDeliveryAuthorisation as Arrangement
from api.modules.delivery import service
from api.modules.identity import capabilities
from api.modules.identity.models import Membership, Tenant, User
from api.modules.marketplace.models import Course
from api.modules.notifications.models import Notification


@dataclass
class World:
    seller: uuid.UUID
    partner: uuid.UUID
    seller_slug: str
    seller_owner: uuid.UUID
    partner_owner: uuid.UUID
    course: uuid.UUID


@pytest.fixture
async def world() -> AsyncIterator[World]:
    suffix = uuid.uuid4().hex[:10]
    async with get_sessionmaker()() as db:
        seller = Tenant(
            slug=f"dr-s-{suffix}", name=f"Race Seller {suffix}", tenant_type="course_provider",
            publishes_courses=True, delivers_training=False,
        )  # fmt: skip
        partner = Tenant(
            slug=f"dr-p-{suffix}", name=f"Race Partner {suffix}", tenant_type="course_provider",
            publishes_courses=False, delivers_training=True,
        )  # fmt: skip
        users = [
            User(email=f"dr-{suffix}-{i}@iism-fixtures.co.in", full_name=f"Owner {i}")
            for i in range(2)
        ]
        db.add_all([seller, partner, *users])
        await db.flush()
        db.add_all(
            [
                Membership(user_id=users[0].id, tenant_id=seller.id, role="owner"),
                Membership(user_id=users[1].id, tenant_id=partner.id, role="owner"),
            ]
        )
        course = Course(tenant_id=seller.id, slug=f"dr-c-{suffix}", title="Race course")
        db.add(course)
        await db.commit()
        made = World(seller.id, partner.id, seller.slug, users[0].id, users[1].id, course.id)
    try:
        yield made
    finally:
        async with get_sessionmaker()() as db:
            ids = [made.seller, made.partner]
            await db.execute(delete(Notification).where(Notification.recipient_id.in_(ids)))
            await db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.subject_id.in_(ids)))
            await db.execute(delete(Arrangement).where(Arrangement.provider_id.in_(ids)))
            await db.execute(delete(Course).where(Course.id == made.course))
            await db.execute(delete(Membership).where(Membership.tenant_id.in_(ids)))
            await db.execute(delete(Tenant).where(Tenant.id.in_(ids)))
            await db.execute(
                delete(User).where(User.id.in_([made.seller_owner, made.partner_owner]))
            )
            await db.commit()


async def _ask(world: World) -> int:
    async with get_sessionmaker()() as db:
        partner = await db.get(Tenant, world.partner)
        actor = await db.get(User, world.partner_owner)
        assert partner is not None and actor is not None
        try:
            await service.request_delivery(
                db, partner=partner, actor=actor, provider_slug=world.seller_slug, course_slug=None
            )
        except HTTPException as refusal:
            return refusal.status_code
        return 201


async def _row_id(world: World) -> uuid.UUID:
    async with get_sessionmaker()() as db:
        row = await db.scalar(select(Arrangement.id).where(Arrangement.provider_id == world.seller))
        assert row is not None
        return row


async def test_a_double_tap_makes_one_request_and_a_409(world: World, monkeypatch) -> None:
    """Both read "nothing open" and both insert; the unique index refuses the second."""
    # The pre-check would catch a *sequential* duplicate; here the window is held open between the
    # check and the insert so both pass it, which is the race the index exists for.
    original = service._lock_parties

    async def slow(db, provider_id, partner_id):  # type: ignore[no-untyped-def]
        await original(db, provider_id, partner_id)
        await asyncio.sleep(0.3)

    monkeypatch.setattr(service, "_lock_parties", slow)
    results = await asyncio.gather(_ask(world), _ask(world))
    assert sorted(results) == [201, 409]
    async with get_sessionmaker()() as db:
        rows = (
            await db.scalars(select(Arrangement).where(Arrangement.provider_id == world.seller))
        ).all()
    assert len(rows) == 1


async def _approve(world: World) -> int:
    async with get_sessionmaker()() as db:
        seller = await db.get(Tenant, world.seller)
        actor = await db.get(User, world.seller_owner)
        assert seller is not None and actor is not None
        try:
            await service.approve(
                db, provider=seller, actor=actor, authorisation_id=await _row_id(world)
            )
        except HTTPException as refusal:
            return refusal.status_code
        return 200


async def _withdraw(world: World) -> int:
    async with get_sessionmaker()() as db:
        partner = await db.get(Tenant, world.partner)
        actor = await db.get(User, world.partner_owner)
        assert partner is not None and actor is not None
        try:
            await service.decline(
                db, org=partner, actor=actor, authorisation_id=await _row_id(world)
            )
        except HTTPException as refusal:
            return refusal.status_code
        return 200


async def test_approve_and_withdraw_at_once_leave_exactly_one_outcome(
    world: World, monkeypatch
) -> None:
    assert await _ask(world) == 201
    original = service._locked

    async def slow(db, org, authorisation_id):  # type: ignore[no-untyped-def]
        row = await original(db, org, authorisation_id)
        await asyncio.sleep(0.4)
        return row

    monkeypatch.setattr(service, "_locked", slow)
    results = await asyncio.gather(_approve(world), _withdraw(world))
    assert sorted(results) == [200, 409], "one acts; the other is told what it now is"
    async with get_sessionmaker()() as db:
        row = await db.get(Arrangement, await _row_id(world))
    assert row is not None and row.state in ("approved", "declined")
    assert (row.state == "approved") == (results[0] == 200), "the winner is the state"


@pytest.fixture
def _slow_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    original = capabilities.delivery_in_progress

    async def slow(db, tenant):  # type: ignore[no-untyped-def]
        answer = await original(db, tenant)
        await asyncio.sleep(0.5)
        return answer

    monkeypatch.setattr(capabilities, "delivery_in_progress", slow)


async def test_a_request_and_delivery_being_switched_off_never_both_land(
    world: World, _slow_capability: None
) -> None:
    """The owner switches delivery off (counting arrangements, slowly); a request arrives."""
    # Make the partner able to stop delivering at all (it also sells), before the race starts.
    async with get_sessionmaker()() as db:
        partner = await db.get(Tenant, world.partner)
        assert partner is not None
        partner.publishes_courses = True
        await db.commit()

    async def off() -> int:
        async with get_sessionmaker()() as db:
            partner = await db.get(Tenant, world.partner)
            actor = await db.get(User, world.partner_owner)
            assert partner is not None and actor is not None
            try:
                await capabilities.set_capabilities(
                    db, tenant=partner, actor=actor, delivers_training=False
                )
            except HTTPException as refusal:
                return refusal.status_code
            return 200

    stopping = asyncio.create_task(off())
    await asyncio.sleep(0.15)
    asked = await _ask(world)
    stopped = await stopping
    async with get_sessionmaker()() as db:
        delivers = await db.scalar(
            select(Tenant.delivers_training).where(Tenant.id == world.partner)
        )
        open_rows = (
            await db.scalars(select(Arrangement).where(Arrangement.partner_id == world.partner))
        ).all()
    assert stopped == 200 and asked == 404, "the flag went off first: the request is refused"
    assert delivers is False and open_rows == []


async def test_delivery_being_switched_off_waits_for_a_request_already_landing(
    world: World, monkeypatch
) -> None:
    """The other order: the request holds the share lock, so the owner's count sees its row."""
    async with get_sessionmaker()() as db:
        partner = await db.get(Tenant, world.partner)
        assert partner is not None
        partner.publishes_courses = True
        await db.commit()
    original = service._lock_parties

    async def slow(db, provider_id, partner_id):  # type: ignore[no-untyped-def]
        await original(db, provider_id, partner_id)
        await asyncio.sleep(0.5)

    monkeypatch.setattr(service, "_lock_parties", slow)

    async def off() -> int:
        async with get_sessionmaker()() as db:
            partner = await db.get(Tenant, world.partner)
            actor = await db.get(User, world.partner_owner)
            assert partner is not None and actor is not None
            try:
                await capabilities.set_capabilities(
                    db, tenant=partner, actor=actor, delivers_training=False
                )
            except HTTPException as refusal:
                return refusal.status_code
            return 200

    asking = asyncio.create_task(_ask(world))
    await asyncio.sleep(0.15)
    stopped = await off()
    asked = await asking
    assert asked == 201 and stopped == 409, "the request landed first: the owner is told it is open"
