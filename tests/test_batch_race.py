"""Sprint 98, ADR-103: a batch being planned while the ground under it moves.

Three races, each with a lock as arbiter and each shown to fail without it:

* **A batch against the arrangement ending.** `authorises(lock=True)` share-locks the covering rows
  and `revoke` takes `FOR UPDATE` on the same one, so either the batch exists before the sweep looks
  (and is cancelled by it) or finds the arrangement ended (and is refused). Never a live batch under
  an arrangement that no longer exists.
* **Two publishes of one draft.** The batch row is locked and re-read: one wins, the other is told
  what the batch now is.
* **A batch against its centre closing.** `create_batch` share-locks the centre and `close_centre`
  takes the stronger lock before counting: the batch is counted (the close is refused) or finds the
  centre closed (and is refused).

Real concurrency on committed rows (the suite's `db` fixture is one connection and cannot show it),
with the window held open on purpose so the interleaving does not depend on scheduler timing.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from api.core.clock import today_ist
from api.core.database import get_sessionmaker
from api.modules.analytics.models import AnalyticsEvent
from api.modules.batches import service
from api.modules.batches.models import Batch
from api.modules.batches.schemas import BatchIn
from api.modules.centres import service as centres
from api.modules.delivery import CourseDeliveryAuthorisation as Arrangement
from api.modules.delivery import service as delivery
from api.modules.identity.models import Membership, Tenant, User
from api.modules.marketplace.models import Course
from api.modules.notifications.models import Notification


@dataclass
class World:
    seller: uuid.UUID
    partner: uuid.UUID
    centre: uuid.UUID
    seller_owner: uuid.UUID
    partner_owner: uuid.UUID
    course: uuid.UUID
    course_slug: str
    centre_slug: str
    arrangement: uuid.UUID


@pytest.fixture
async def world() -> AsyncIterator[World]:
    suffix = uuid.uuid4().hex[:10]
    async with get_sessionmaker()() as db:
        seller = Tenant(
            slug=f"br-s-{suffix}", name=f"Batch Seller {suffix}", tenant_type="course_provider",
            publishes_courses=True, delivers_training=False,
        )  # fmt: skip
        partner = Tenant(
            slug=f"br-p-{suffix}", name=f"Batch Partner {suffix}", tenant_type="course_provider",
            publishes_courses=False, delivers_training=True,
        )  # fmt: skip
        users = [
            User(email=f"br-{suffix}-{i}@iism-fixtures.co.in", full_name=f"Owner {i}")
            for i in range(2)
        ]
        db.add_all([seller, partner, *users])
        await db.flush()
        centre = Tenant(
            slug=f"br-c-{suffix}", name=f"Batch Centre {suffix}", tenant_type="training_centre",
            parent_id=partner.id,
        )  # fmt: skip
        course = Course(
            tenant_id=seller.id, slug=f"br-k-{suffix}", title="Race course", status="published"
        )
        db.add_all(
            [
                centre,
                course,
                Membership(user_id=users[0].id, tenant_id=seller.id, role="owner"),
                Membership(user_id=users[1].id, tenant_id=partner.id, role="owner"),
            ]
        )
        await db.flush()
        now = datetime.now(UTC)
        arrangement = Arrangement(
            provider_id=seller.id,
            partner_id=partner.id,
            course_id=None,
            initiated_by="provider",
            requested_at=now,
            requested_by=users[0].id,
            approved_at=now,
            approved_by=users[0].id,
        )
        db.add(arrangement)
        await db.commit()
        made = World(
            seller.id, partner.id, centre.id, users[0].id, users[1].id, course.id,
            course.slug, centre.slug, arrangement.id,
        )  # fmt: skip
    try:
        yield made
    finally:
        async with get_sessionmaker()() as db:
            ids = [made.seller, made.partner, made.centre]
            await db.execute(delete(Batch).where(Batch.centre_id == made.centre))
            await db.execute(delete(Notification).where(Notification.recipient_id.in_(ids)))
            await db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.subject_id.in_(ids)))
            await db.execute(delete(Arrangement).where(Arrangement.provider_id == made.seller))
            await db.execute(delete(Course).where(Course.id == made.course))
            await db.execute(delete(Membership).where(Membership.tenant_id.in_(ids)))
            await db.execute(delete(Tenant).where(Tenant.id == made.centre))
            await db.execute(delete(Tenant).where(Tenant.id.in_([made.seller, made.partner])))
            await db.execute(
                delete(User).where(User.id.in_([made.seller_owner, made.partner_owner]))
            )
            await db.commit()


def _plan(world: World) -> BatchIn:
    start = today_ist() + timedelta(days=14)
    return BatchIn(
        course_slug=world.course_slug,
        centre_slug=world.centre_slug,
        seats=10,
        starts_on=start,
        ends_on=start + timedelta(days=30),
    )


async def _create(world: World) -> int:
    async with get_sessionmaker()() as db:
        partner = await db.get(Tenant, world.partner)
        actor = await db.get(User, world.partner_owner)
        assert partner is not None and actor is not None
        try:
            await service.create_batch(db, partner, actor, _plan(world))
        except HTTPException as refusal:
            return refusal.status_code
        return 201


async def _revoke(world: World) -> int:
    async with get_sessionmaker()() as db:
        seller = await db.get(Tenant, world.seller)
        actor = await db.get(User, world.seller_owner)
        assert seller is not None and actor is not None
        try:
            await delivery.revoke(db, org=seller, actor=actor, authorisation_id=world.arrangement)
        except HTTPException as refusal:
            return refusal.status_code
        return 200


async def _batches(world: World) -> list[Batch]:
    async with get_sessionmaker()() as db:
        return list((await db.scalars(select(Batch).where(Batch.centre_id == world.centre))).all())


def _hold(monkeypatch: pytest.MonkeyPatch, module, name: str, seconds: float = 0.6) -> None:  # type: ignore[no-untyped-def]
    """Wrap `module.name` so it sleeps **after** doing its work, inside the caller's transaction:
    whatever lock it took is held for the whole pause."""
    original = getattr(module, name)

    async def slow(*args, **kwargs):  # type: ignore[no-untyped-def]
        answer = await original(*args, **kwargs)
        await asyncio.sleep(seconds)
        return answer

    monkeypatch.setattr(module, name, slow)


async def test_a_batch_being_made_is_cancelled_by_the_revocation_that_follows(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hold(monkeypatch, service, "_require_may_deliver")
    creating = asyncio.create_task(_create(world))
    await asyncio.sleep(0.2)
    revoked = await _revoke(world)
    assert await creating == 201 and revoked == 200
    rows = await _batches(world)
    assert len(rows) == 1
    assert (rows[0].status, rows[0].cancel_reason) == ("cancelled", "arrangement_ended"), (
        "the batch landed first, so the sweep found it: never a live batch under an ended approval"
    )


async def test_a_revocation_in_progress_refuses_the_batch_that_follows(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hold(monkeypatch, delivery, "_notify_other")
    revoking = asyncio.create_task(_revoke(world))
    await asyncio.sleep(0.2)
    created = await _create(world)
    assert await revoking == 200
    assert created == 403, "the arrangement ended first, so no batch is made under it"
    assert await _batches(world) == []


async def _publish(world: World, batch_id: uuid.UUID) -> int:
    async with get_sessionmaker()() as db:
        partner = await db.get(Tenant, world.partner)
        actor = await db.get(User, world.partner_owner)
        assert partner is not None and actor is not None
        try:
            await service.publish_batch(db, partner, actor, batch_id)
        except HTTPException as refusal:
            return refusal.status_code
        return 200


async def test_two_publishes_of_one_draft_make_one_publication(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await _create(world) == 201
    batch_id = (await _batches(world))[0].id
    _hold(monkeypatch, service, "_require_may_deliver", 0.4)
    results = await asyncio.gather(_publish(world, batch_id), _publish(world, batch_id))
    assert sorted(results) == [200, 409]
    async with get_sessionmaker()() as db:
        published = (
            await db.scalars(
                select(AnalyticsEvent).where(
                    AnalyticsEvent.name == "batch_published",
                    AnalyticsEvent.subject_id == world.partner,
                )
            )
        ).all()
    assert len(published) == 1


async def _close(world: World) -> int:
    async with get_sessionmaker()() as db:
        partner = await db.get(Tenant, world.partner)
        centre = await db.get(Tenant, world.centre)
        actor = await db.get(User, world.partner_owner)
        assert partner is not None and centre is not None and actor is not None
        try:
            await centres.close_centre(db, partner, centre, actor)
        except HTTPException as refusal:
            return refusal.status_code
        return 200


async def test_a_batch_being_made_stops_its_centre_closing(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _hold(monkeypatch, service, "_require_may_deliver")
    creating = asyncio.create_task(_create(world))
    await asyncio.sleep(0.2)
    closed = await _close(world)
    assert await creating == 201
    assert closed == 409, "the batch landed first, so the centre is told it is still in use"
    async with get_sessionmaker()() as db:
        centre = await db.get(Tenant, world.centre)
        assert centre is not None and centre.closed_at is None


async def test_a_centre_closing_stops_a_batch_being_made_there(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.modules import batches

    _hold(monkeypatch, batches, "live_at_centre")
    closing = asyncio.create_task(_close(world))
    await asyncio.sleep(0.2)
    created = await _create(world)
    assert await closing == 200
    assert created == 409, "the centre closed first, so no batch lands in a closed centre"
    assert await _batches(world) == []
