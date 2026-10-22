"""Sprint 95, ADR-102: creating a centre while its organisation stops delivering.

`capability_for` is asked at the start of the request, so a centre created at the instant an owner
turns *delivers training* off could land under an organisation that no longer delivers. Turning it
off takes the ownership lock (`FOR NO KEY UPDATE`) and counts the open centres; creating one
share-locks the organisation and reads the flag again. `FOR SHARE` conflicts with the other, so
exactly one order happens and the loser is told the truth. Real concurrency, committed rows (the
suite's `db` fixture is one connection and cannot show a race).
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
from api.modules.centres import service
from api.modules.centres.schemas import CentreIn
from api.modules.identity import capabilities
from api.modules.identity.models import Membership, Tenant, User


@dataclass
class Org:
    tenant_id: uuid.UUID
    owner: uuid.UUID


@pytest.fixture
async def org() -> AsyncIterator[Org]:
    suffix = uuid.uuid4().hex[:10]
    async with get_sessionmaker()() as db:
        tenant = Tenant(
            slug=f"cr-{suffix}",
            name=f"Centre Race {suffix}",
            tenant_type="course_provider",
            publishes_courses=True,
            delivers_training=True,
        )
        user = User(email=f"cr-{suffix}@iism-fixtures.co.in", full_name="Owner")
        db.add_all([tenant, user])
        await db.flush()
        db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
        await db.commit()
        made = Org(tenant.id, user.id)
    try:
        yield made
    finally:
        async with get_sessionmaker()() as db:
            await db.execute(delete(Tenant).where(Tenant.parent_id == made.tenant_id))
            await db.execute(
                delete(AnalyticsEvent).where(AnalyticsEvent.subject_id == made.tenant_id)
            )
            await db.execute(delete(Membership).where(Membership.tenant_id == made.tenant_id))
            await db.execute(delete(Tenant).where(Tenant.id == made.tenant_id))
            await db.execute(delete(User).where(User.id == made.owner))
            await db.commit()


@pytest.fixture
def _slow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold each side open for a moment inside whatever protects it."""
    full = service.refuse_if_full
    delivering = capabilities.delivery_in_progress

    async def slow_full(db, parent):  # type: ignore[no-untyped-def]
        await full(db, parent)
        await asyncio.sleep(0.5)

    async def slow_delivering(db, tenant):  # type: ignore[no-untyped-def]
        answer = await delivering(db, tenant)
        await asyncio.sleep(0.5)
        return answer

    monkeypatch.setattr(service, "refuse_if_full", slow_full)
    monkeypatch.setattr(capabilities, "delivery_in_progress", slow_delivering)


async def _create(org: Org, name: str) -> int:
    async with get_sessionmaker()() as db:
        tenant = await db.get(Tenant, org.tenant_id)
        actor = await db.get(User, org.owner)
        assert tenant is not None and actor is not None
        try:
            await service.create_centre(
                db, tenant, actor, CentreIn(name=name, state="Nowhere", district="Noplace")
            )
        except HTTPException as refusal:
            return refusal.status_code
        return 201


async def _stop_delivering(org: Org) -> int:
    async with get_sessionmaker()() as db:
        tenant = await db.get(Tenant, org.tenant_id)
        actor = await db.get(User, org.owner)
        assert tenant is not None and actor is not None
        try:
            await capabilities.set_capabilities(
                db, tenant=tenant, actor=actor, delivers_training=False
            )
        except HTTPException as refusal:
            return refusal.status_code
        return 200


async def _state(org: Org) -> tuple[bool, int]:
    async with get_sessionmaker()() as db:
        delivers = await db.scalar(
            select(Tenant.delivers_training).where(Tenant.id == org.tenant_id)
        )
        centres = await service.centre_count(db, org.tenant_id)
        return bool(delivers), centres


async def test_a_centre_being_created_stops_the_owner_turning_delivery_off(
    org: Org, _slow: None
) -> None:
    created = asyncio.create_task(_create(org, "Early Centre"))
    await asyncio.sleep(0.15)
    stopped = await _stop_delivering(org)
    assert await created == 201
    assert stopped == 409, "the centre landed first, so the owner is told it is open"
    assert await _state(org) == (True, 1)


async def test_delivery_being_turned_off_stops_a_centre_being_created(
    org: Org, _slow: None
) -> None:
    stopping = asyncio.create_task(_stop_delivering(org))
    await asyncio.sleep(0.15)
    created = await _create(org, "Late Centre")
    assert await stopping == 200
    assert created == 403, "the flag went off first, so no centre lands under it"
    assert await _state(org) == (False, 0)
