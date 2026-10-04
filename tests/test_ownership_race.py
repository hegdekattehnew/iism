"""Sprint 44, BL-9.1: two owners acting at once must not empty the room.

`_refuse_if_last_owner` counted owners in one statement and the caller wrote in
another, with nothing between them. Under READ COMMITTED two owners acting at the
same moment each see two owners and each pass: A demotes B while B demotes A, or
both leave, and the organisation has **nobody in charge** -- the exact outcome
Sprint 25 was built to make impossible.

These tests need real concurrency, which the suite's `db` fixture cannot give:
it wraps one connection in one transaction that is always rolled back. So they
build an organisation with **committed** rows through the service's own
sessionmaker, run two sessions at once, and delete what they made.

The window is widened on purpose (`_slow_count`): without it the interleaving
depends on scheduler timing and the test would pass by luck on a quiet machine.
The window sits *after* the count and *inside* whatever protects it, so a lock
makes the second caller wait rather than letting both through.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select

from api.core.database import get_sessionmaker
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import invitations
from api.modules.identity.models import Membership, Tenant, User


@dataclass
class Org:
    tenant_id: uuid.UUID
    owners: list[uuid.UUID]
    others: list[uuid.UUID]


async def _make_org(owners: int, others: int = 0) -> Org:
    suffix = uuid.uuid4().hex[:10]
    async with get_sessionmaker()() as db:
        tenant = Tenant(
            slug=f"race-{suffix}", name=f"Race Fixtures {suffix}", tenant_type="employer"
        )
        db.add(tenant)
        await db.flush()
        users: list[tuple[User, str]] = []
        for i in range(owners + others):
            user = User(email=f"race-{suffix}-{i}@iism-fixtures.co.in", full_name=f"Person {i}")
            db.add(user)
            users.append((user, "owner" if i < owners else "member"))
        await db.flush()
        for user, role in users:
            db.add(Membership(user_id=user.id, tenant_id=tenant.id, role=role))
        await db.commit()
        ids = [u.id for u, _ in users]
        return Org(tenant.id, ids[:owners], ids[owners:])


async def _erase(org: Org) -> None:
    async with get_sessionmaker()() as db:
        ids = org.owners + org.others
        await db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.subject_id == org.tenant_id))
        await db.execute(delete(Membership).where(Membership.tenant_id == org.tenant_id))
        await db.execute(delete(Tenant).where(Tenant.id == org.tenant_id))
        await db.execute(delete(User).where(User.id.in_(ids)))
        await db.commit()


@pytest.fixture
async def two_owners() -> AsyncIterator[Org]:
    org = await _make_org(owners=2)
    try:
        yield org
    finally:
        await _erase(org)


@pytest.fixture
def _slow_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold every owner count open for a moment after it has been answered."""
    original = invitations._owner_count

    async def slow(db, tenant_id):  # type: ignore[no-untyped-def]
        counted = await original(db, tenant_id)
        await asyncio.sleep(0.4)
        return counted

    monkeypatch.setattr(invitations, "_owner_count", slow)


async def _owners_left(tenant_id: uuid.UUID) -> int:
    async with get_sessionmaker()() as db:
        return (
            await db.scalar(
                select(func.count())
                .select_from(Membership)
                .where(Membership.tenant_id == tenant_id, Membership.role == "owner")
            )
        ) or 0


async def _attempt(coro) -> int:  # type: ignore[no-untyped-def]
    try:
        await coro
    except HTTPException as refusal:
        return refusal.status_code
    return 200


class TestTwoOwnersAtOnce:
    async def test_mutual_demotion_leaves_somebody_in_charge(
        self, two_owners: Org, _slow_count: None
    ) -> None:
        a, b = two_owners.owners

        async def demote(actor: uuid.UUID, target: uuid.UUID) -> int:
            async with get_sessionmaker()() as db:
                return await _attempt(
                    invitations.set_role(
                        db,
                        tenant_id=two_owners.tenant_id,
                        actor_user_id=actor,
                        user_id=target,
                        role="admin",
                    )
                )

        outcomes = await asyncio.gather(demote(a, b), demote(b, a))

        assert await _owners_left(two_owners.tenant_id) == 1, outcomes
        # One went through. The other was refused -- as a former owner, not as
        # the last one, because the first demotion had already taken their role.
        assert sorted(outcomes) == [200, 403]

    async def test_both_owners_leaving_at_once_leaves_somebody(
        self, two_owners: Org, _slow_count: None
    ) -> None:
        a, b = two_owners.owners

        async def leave(user_id: uuid.UUID) -> int:
            async with get_sessionmaker()() as db:
                user = await db.get(User, user_id)
                assert user is not None
                return await _attempt(
                    invitations.leave(db, tenant_id=two_owners.tenant_id, user=user)
                )

        outcomes = await asyncio.gather(leave(a), leave(b))

        assert await _owners_left(two_owners.tenant_id) == 1, outcomes
        assert sorted(outcomes) == [200, 409]

    async def test_an_owner_who_was_demoted_meanwhile_cannot_still_act_as_one(self) -> None:
        """Authority is checked when the request arrives, then used some time
        later. An owner demoted in between must not complete an owner-only act."""
        org = await _make_org(owners=2, others=1)
        try:
            a, b = org.owners
            (target,) = org.others
            async with get_sessionmaker()() as db:
                await invitations.set_role(
                    db, tenant_id=org.tenant_id, actor_user_id=a, user_id=b, role="admin"
                )
            async with get_sessionmaker()() as db:
                # `b` passed the route's permission check a moment ago, as an owner.
                with pytest.raises(HTTPException) as refused:
                    await invitations.set_role(
                        db,
                        tenant_id=org.tenant_id,
                        actor_user_id=b,
                        user_id=target,
                        role="admin",
                    )
                assert refused.value.status_code == 403
            async with get_sessionmaker()() as db:
                with pytest.raises(HTTPException) as refused_removal:
                    await invitations.remove_member(
                        db, tenant_id=org.tenant_id, actor_user_id=b, user_id=target
                    )
                assert refused_removal.value.status_code == 403
        finally:
            await _erase(org)


class TestErasureAgainstLeaving:
    """Account erasure asks the last-owner question through its own grouped count,
    not `_owner_count`, so the lock has to be taken there as well."""

    async def test_an_owner_erasing_themselves_while_the_other_leaves(
        self, two_owners: Org, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.modules.privacy import service as privacy

        original = privacy._membership_counts

        async def slow(db, tenant_ids, user_id):  # type: ignore[no-untyped-def]
            counted = await original(db, tenant_ids, user_id)
            await asyncio.sleep(0.4)
            return counted

        monkeypatch.setattr(privacy, "_membership_counts", slow)
        a, b = two_owners.owners

        async def erase(user_id: uuid.UUID) -> int:
            async with get_sessionmaker()() as db:
                user = await db.get(User, user_id)
                assert user is not None
                return await _attempt(privacy.delete_account(db, user))

        async def leave(user_id: uuid.UUID) -> int:
            async with get_sessionmaker()() as db:
                user = await db.get(User, user_id)
                assert user is not None
                return await _attempt(
                    invitations.leave(db, tenant_id=two_owners.tenant_id, user=user)
                )

        outcomes = await asyncio.gather(erase(a), leave(b))

        # Either somebody is still in charge, or the organisation went because
        # the last person out was alone in it -- never a tenant nobody can run.
        async with get_sessionmaker()() as db:
            tenant_alive = await db.get(Tenant, two_owners.tenant_id) is not None
        if tenant_alive:
            assert await _owners_left(two_owners.tenant_id) >= 1, outcomes
