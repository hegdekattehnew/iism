"""Sprint 44, BL-9.1: handing an organisation over is one act.

Until now it was two -- promote a colleague, then leave -- and the second could
fail on its own. The race that made *that* unsafe is in `test_ownership_race.py`;
this file is the act itself: who may do it, to whom, what it records and says,
and that it happens whole or not at all.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity.models import Membership, Tenant
from api.modules.notifications import drain
from api.modules.notifications.models import Notification
from tests.test_invitations import (
    _accept_as_new_account,
    _email,
    _invite,
    _sign_in,
)

Org = tuple[dict[str, str], str]


@pytest.fixture
async def owner(client: AsyncClient) -> Org:
    return await _sign_in(client, _email("owner"), "Handover Fixtures Ltd")


async def _colleague(
    client: AsyncClient, db: AsyncSession, owner: Org, role: str = "admin"
) -> tuple[dict[str, str], str, str]:
    """Somebody who has joined: headers, user id, address."""
    address = _email("colleague")
    headers = await _accept_as_new_account(
        client, db, await _invite(client, owner, address, role=role), address
    )
    me = (await client.get("/auth/me", headers=headers)).json()
    return headers, me["id"], address


async def _transfer(client: AsyncClient, owner: Org, user_id: str, then: str | None = None):  # type: ignore[no-untyped-def]
    headers, slug = owner
    body: dict[str, str] = {"user_id": user_id}
    if then is not None:
        body["then"] = then
    return await client.post(f"/org/{slug}/transfer-ownership", headers=headers, json=body)


async def _roles(client: AsyncClient, as_whom: dict[str, str], slug: str) -> dict[str, str]:
    members = (await client.get(f"/org/{slug}/members", headers=as_whom)).json()
    return {m["user_id"]: m["role"] for m in members}


class TestHandingOver:
    async def test_the_default_is_to_stay_as_an_admin(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        headers, slug = owner
        me = (await client.get("/auth/me", headers=headers)).json()["id"]
        successor, successor_id, _ = await _colleague(client, db, owner)

        response = await _transfer(client, owner, successor_id)

        assert response.status_code == 200, response.text
        assert response.json()["user_id"] == successor_id
        assert response.json()["role"] == "owner"
        assert await _roles(client, successor, slug) == {successor_id: "owner", me: "admin"}

    async def test_or_to_leave(self, client: AsyncClient, db: AsyncSession, owner: Org) -> None:
        headers, slug = owner
        tenant_id = await db.scalar(select(Tenant.id).where(Tenant.slug == slug))
        successor, successor_id, _ = await _colleague(client, db, owner)

        assert (await _transfer(client, owner, successor_id, "leave")).status_code == 200

        assert await _roles(client, successor, slug) == {successor_id: "owner"}
        # Asked of the table, not of `/auth/me`: the suite shares one session across
        # requests, so a user's already-loaded `memberships` list would still show
        # the row this request deleted -- a test artefact, not what a request sees.
        me = (await client.get("/auth/me", headers=headers)).json()["id"]
        left = await db.scalar(
            select(Membership.id).where(
                Membership.user_id == uuid.UUID(me), Membership.tenant_id == tenant_id
            )
        )
        assert left is None

    async def test_a_plain_member_can_be_made_the_owner(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        """Nothing requires the successor to have been an admin first."""
        successor, successor_id, _ = await _colleague(client, db, owner, role="member")
        assert (await _transfer(client, owner, successor_id)).status_code == 200
        assert (
            await client.patch(
                f"/org/{owner[1]}/members/{successor_id}",
                headers=successor,
                json={"role": "member"},
            )
        ).status_code == 409  # the only owner now: the old guard still stands

    async def test_afterwards_the_new_owner_can_do_what_only_an_owner_can(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        headers, slug = owner
        successor, successor_id, _ = await _colleague(client, db, owner)
        await _transfer(client, owner, successor_id)

        invited = await client.post(
            f"/org/{slug}/invitations",
            headers=successor,
            json={"email": _email("third"), "role": "admin"},
        )
        assert invited.status_code == 201
        # ...and the person who handed over no longer can.
        again = await client.post(
            f"/org/{slug}/invitations",
            headers=headers,
            json={"email": _email("fourth"), "role": "admin"},
        )
        assert again.status_code == 403


class TestWhoMayBeChosen:
    async def test_not_yourself(self, client: AsyncClient, owner: Org) -> None:
        me = (await client.get("/auth/me", headers=owner[0])).json()["id"]
        assert (await _transfer(client, owner, me)).status_code == 422

    async def test_not_somebody_who_is_not_a_member(self, client: AsyncClient, owner: Org) -> None:
        assert (await _transfer(client, owner, str(uuid.uuid4()))).status_code == 404

    async def test_not_somebody_who_has_only_been_invited(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        """An invitation cannot carry `owner`, and handing an organisation to an
        address that has not proved it holds the mailbox is how it ends up owned
        by a typo. They have to join first."""
        await _invite(client, owner, _email("pending"), role="admin")
        stranger = await _sign_in(client, _email("elsewhere"), "Elsewhere Ltd")
        stranger_id = (await client.get("/auth/me", headers=stranger[0])).json()["id"]
        assert (await _transfer(client, owner, stranger_id)).status_code == 404

    async def test_not_somebody_who_already_owns_it(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        _, successor_id, _ = await _colleague(client, db, owner)
        await client.patch(
            f"/org/{owner[1]}/members/{successor_id}",
            headers=owner[0],
            json={"role": "owner"},
        )
        refused = await _transfer(client, owner, successor_id)
        assert refused.status_code == 409
        assert "already an owner" in refused.json()["detail"]


class TestWhoMayDoIt:
    async def test_an_admin_may_not(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        admin, _, _ = await _colleague(client, db, owner, role="admin")
        member, member_id, _ = await _colleague(client, db, owner, role="member")
        refused = await client.post(
            f"/org/{owner[1]}/transfer-ownership",
            headers=admin,
            json={"user_id": member_id},
        )
        assert refused.status_code == 403
        assert member  # the member exists and was not made anything

    async def test_a_stranger_gets_the_answer_an_unrouted_organisation_gets(
        self, client: AsyncClient, owner: Org
    ) -> None:
        """ADR-038: a 403 would confirm the organisation exists."""
        stranger, _ = await _sign_in(client, _email("stranger"), "Stranger Ltd")
        body = {"user_id": str(uuid.uuid4())}
        real = await client.post(f"/org/{owner[1]}/transfer-ownership", headers=stranger, json=body)
        unrouted = await client.post(
            "/org/no-such-organisation-anywhere/transfer-ownership", headers=stranger, json=body
        )
        assert real.status_code == unrouted.status_code == 404
        assert real.json() == unrouted.json()

    async def test_nothing_without_signing_in(self, client: AsyncClient, owner: Org) -> None:
        response = await client.post(
            f"/org/{owner[1]}/transfer-ownership", json={"user_id": str(uuid.uuid4())}
        )
        assert response.status_code == 401


class TestWhatItRecordsAndSays:
    async def test_one_event_for_one_act(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        """`member_role_changed` as well would count one decision twice."""
        headers, slug = owner
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        _, successor_id, _ = await _colleague(client, db, owner)
        await _transfer(client, owner, successor_id, "leave")

        rows = (
            await db.scalars(
                select(AnalyticsEvent).where(
                    AnalyticsEvent.subject_id == tenant.id,
                    AnalyticsEvent.name.in_(["ownership_transferred", "member_role_changed"]),
                )
            )
        ).all()
        assert [r.name for r in rows] == ["ownership_transferred"]
        assert rows[0].payload == {"then": "leave"}
        assert rows[0].subject_type == "tenant"
        # The person it happened to is in no payload: an event names the act.
        assert successor_id not in str(rows[0].payload)

    async def test_a_refused_transfer_records_nothing(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        me = (await client.get("/auth/me", headers=owner[0])).json()["id"]
        await _transfer(client, owner, me)
        count = await db.scalar(
            select(AnalyticsEvent.id).where(AnalyticsEvent.name == "ownership_transferred")
        )
        assert count is None

    async def test_the_new_owner_is_told_without_an_address_in_the_payload(
        self, client: AsyncClient, db: AsyncSession, owner: Org
    ) -> None:
        _, slug = owner
        _, successor_id, _ = await _colleague(client, db, owner)
        await _transfer(client, owner, successor_id)

        rows = (
            await db.scalars(
                select(Notification).where(Notification.template == "ownership_received")
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].recipient_kind == "user"
        assert str(rows[0].recipient_id) == successor_id
        assert rows[0].channel == "email"
        assert rows[0].payload == {
            "organisation": "Handover Fixtures Ltd",
            "path": f"/employer/{slug}/team",
        }
        assert "@" not in str(rows[0].payload)

    async def test_the_email_reaches_the_new_owners_address(
        self,
        client: AsyncClient,
        db: AsyncSession,
        owner: Org,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import api.modules.notifications.service as notifications

        _, slug = owner
        _, successor_id, address = await _colleague(client, db, owner)
        await _transfer(client, owner, successor_id)
        sent: list[tuple[str, str, str]] = []

        class Recording:
            async def send_email(self, to: str, subject: str, body: str) -> None:
                sent.append((to, subject, body))

        monkeypatch.setattr(notifications, "get_email_provider", lambda: Recording())
        await drain(db)

        (to, subject, body) = next(m for m in sent if m[0] == address)
        assert "Handover Fixtures Ltd" in subject
        assert f"/employer/{slug}/team" in body

    async def test_the_notice_is_queued_before_the_handover_commits(
        self, client: AsyncClient, db: AsyncSession, owner: Org, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In the handover's own transaction: a notice that cannot be written must
        not leave somebody an owner in silence, and a commit that came first could
        not be undone by a failed enqueue."""
        import api.modules.notifications as notifications

        _, successor_id, _ = await _colleague(client, db, owner)
        order: list[str] = []
        real_enqueue, real_commit = notifications.enqueue, db.commit

        async def spy_enqueue(*args: object, **kwargs: object) -> object:
            order.append("enqueue")
            return await real_enqueue(*args, **kwargs)  # type: ignore[arg-type]

        async def spy_commit() -> None:
            order.append("commit")
            await real_commit()

        monkeypatch.setattr(notifications, "enqueue", spy_enqueue)
        monkeypatch.setattr(db, "commit", spy_commit)
        await _transfer(client, owner, successor_id)

        assert order[:2] == ["enqueue", "commit"]
