"""Sprint 25: an organisation can have more than one person in it.

For twenty-four sprints every `Membership` was written with `role="owner"` by
one of three call sites, no endpoint touched the table, and `admin` and
`member` were fully mapped permission sets that nothing could reach. The
consequence was not inconvenience but data loss: a sole owner deleting their
account destroyed the organisation, its listings and **every application to
them**, and the 409 meant to stop it needed a second owner to exist.

Four things here are worth more than the rest, and each is a defect this
project has already shipped once in some other form:

* **the response is identical for a known and an unknown address** (Sprint 12's
  enumeration oracle);
* **an unknown address with no invitation still gets 401** from
  `verify_email_and_sign_in` -- that refusal is load-bearing and this sprint
  edited the function around it;
* **the last owner cannot be removed, demoted or leave**, asked once in the
  service rather than three times in three handlers (Sprint 15);
* **a new account created by accepting has its consent recorded**, or every
  request it makes afterwards is a 428 (Sprint 20).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity.models import Invitation, Tenant, User
from api.modules.notifications.models import Notification


def _email(prefix: str = "org") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"


async def _sign_in(client: AsyncClient, address: str, name: str) -> tuple[dict[str, str], str]:
    """Register an organisation by email and return its headers and slug."""
    requested = await client.post(
        "/auth/org/register",
        json={
            "email": address,
            "organisation_name": name,
            "tenant_type": "employer",
            "consent_version": CONSENT,
        },
    )
    code = requested.json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/auth/me", headers=headers)).json()
    slug = next(m["tenant"]["slug"] for m in me["memberships"])
    return headers, slug


@pytest.fixture
async def owner(client: AsyncClient) -> tuple[dict[str, str], str]:
    return await _sign_in(client, _email("owner"), "Apollo Care Fixtures")


async def _invite(
    client: AsyncClient, owner: tuple[dict[str, str], str], address: str, role: str = "member"
) -> dict:
    headers, slug = owner
    response = await client.post(
        f"/org/{slug}/invitations", headers=headers, json={"email": address, "role": role}
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestInviting:
    async def test_an_owner_invites_somebody(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        address = _email("invitee")
        body = await _invite(client, owner, address)

        assert body["email"] == address
        assert body["role"] == "member"
        assert body["state"] == "pending"
        # The token is never in the response: it reached one mailbox, and a
        # list every colleague with MEMBER_INVITE can read is not the place to
        # hand it to all of them.
        assert "token" not in body

        row = await db.scalar(select(Invitation).where(Invitation.email == address))
        assert row is not None
        assert row.token_hash and address not in row.token_hash
        assert row.expires_at > datetime.now(UTC)

    async def test_the_answer_is_the_same_for_a_known_and_an_unknown_address(
        self, client: AsyncClient, owner: tuple[dict[str, str], str]
    ) -> None:
        """Sprint 12's oracle, which was shipped once and must not return.

        An earlier version of organisation registration made two responses
        differ by one field for a known address, and a prober could read the
        difference straight off the response. Inviting must not reintroduce it.
        """
        stranger = _email("stranger")
        known = _email("known")
        await _sign_in(client, known, "Somebody Else Ltd")

        a = await _invite(client, owner, stranger)
        b = await _invite(client, owner, known)

        # Everything that is not inherently per-row must match exactly.
        volatile = {"id", "email", "created_at", "expires_at"}
        assert {k: v for k, v in a.items() if k not in volatile} == {
            k: v for k, v in b.items() if k not in volatile
        }

    async def test_an_admin_cannot_invite_an_admin(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        """The escalation ceiling. Without it `MEMBER_INVITE` is a route to
        promoting yourself by proxy: invite a second address you control as an
        admin, and the ceiling on your own role has bought nothing."""
        headers, slug = owner
        admin_address = _email("admin")
        admin_headers = await _accept_as_new_account(
            client, db, await _invite(client, owner, admin_address, role="admin"), admin_address
        )

        refused = await client.post(
            f"/org/{slug}/invitations",
            headers=admin_headers,
            json={"email": _email(), "role": "admin"},
        )
        assert refused.status_code == 403

        allowed = await client.post(
            f"/org/{slug}/invitations",
            headers=admin_headers,
            json={"email": _email(), "role": "member"},
        )
        assert allowed.status_code == 201

    async def test_a_member_cannot_invite_at_all(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        _, slug = owner
        address = _email("plain")
        member_headers = await _accept_as_new_account(
            client, db, await _invite(client, owner, address), address
        )
        refused = await client.post(
            f"/org/{slug}/invitations", headers=member_headers, json={"email": _email()}
        )
        assert refused.status_code == 403

    async def test_a_non_member_gets_404_never_403(
        self, client: AsyncClient, owner: tuple[dict[str, str], str]
    ) -> None:
        """ADR-038: a 403 confirms the organisation exists, so an employer
        could enumerate competitors by guessing slugs."""
        _, slug = owner
        outsider, _ = await _sign_in(client, _email("outsider"), "Unrelated Ltd")
        response = await client.post(
            f"/org/{slug}/invitations", headers=outsider, json={"email": _email()}
        )
        assert response.status_code == 404

    async def test_inviting_the_same_address_twice_is_refused(
        self, client: AsyncClient, owner: tuple[dict[str, str], str]
    ) -> None:
        headers, slug = owner
        address = _email("dup")
        await _invite(client, owner, address)
        again = await client.post(
            f"/org/{slug}/invitations", headers=headers, json={"email": address}
        )
        assert again.status_code == 409

    async def test_inviting_an_existing_member_is_refused(
        self, client: AsyncClient, owner: tuple[dict[str, str], str]
    ) -> None:
        headers, slug = owner
        me = (await client.get("/auth/me", headers=headers)).json()
        again = await client.post(
            f"/org/{slug}/invitations", headers=headers, json={"email": me["email"]}
        )
        assert again.status_code == 409

    async def test_the_pending_cap_refuses_the_twenty_first(
        self, client: AsyncClient, owner: tuple[dict[str, str], str]
    ) -> None:
        """The applications-cap pattern: the per-minute write limiter does not
        answer somebody patiently seeding a hundred addresses, each of which
        sends a mail carrying this organisation's name."""
        headers, slug = owner
        for _ in range(20):
            await _invite(client, owner, _email())
        refused = await client.post(
            f"/org/{slug}/invitations", headers=headers, json={"email": _email()}
        )
        assert refused.status_code == 429

    async def test_a_notification_is_queued_to_the_invitation(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        """The outbox keeps its rule: the row names a recipient and holds no
        address. Here the recipient is the invitation, because an invitee may
        have no account to name."""
        body = await _invite(client, owner, _email("mailed"))
        row = await db.scalar(
            select(Notification).where(Notification.recipient_id == uuid.UUID(body["id"]))
        )
        assert row is not None
        assert row.recipient_kind == "invitation"
        assert row.template == "organisation_invitation"
        assert "@" not in str(row.payload)


class TestAccepting:
    async def test_an_existing_account_accepts_and_gains_a_membership(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        _, slug = owner
        address = _email("existing")
        joiner, _ = await _sign_in(client, address, "Their Own Ltd")
        body = await _invite(client, owner, address)
        token = await _plaintext_token(db, client, body)

        accepted = await client.post(f"/invitations/{token}/accept", headers=joiner)
        assert accepted.status_code == 200
        assert accepted.json() == {"organisation_slug": slug, "role": "member"}

        me = (await client.get("/auth/me", headers=joiner)).json()
        # One identity, one more membership -- never a second account.
        assert {m["tenant"]["slug"] for m in me["memberships"]} >= {slug}

    async def test_a_brand_new_address_gets_an_account_with_consent_recorded(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        """The riskiest path in the sprint, and the one Sprint 20's 428 punishes
        if consent is forgotten."""
        _, slug = owner
        address = _email("fresh")
        headers = await _accept_as_new_account(
            client, db, await _invite(client, owner, address), address
        )

        me = (await client.get("/auth/me", headers=headers)).json()
        assert me["email"] == address
        assert me["consent_version"] == CONSENT
        assert me["consented_at"] is not None
        assert {m["tenant"]["slug"] for m in me["memberships"]} == {slug}

    async def test_a_token_works_once(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        address = _email("once")
        joiner, _ = await _sign_in(client, address, "Once Ltd")
        body = await _invite(client, owner, address)
        token = await _plaintext_token(db, client, body)

        first = await client.post(f"/invitations/{token}/accept", headers=joiner)
        assert first.status_code == 200
        second = await client.post(f"/invitations/{token}/accept", headers=joiner)
        assert second.status_code == 410

    async def test_a_revoked_invitation_is_gone(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        headers, slug = owner
        address = _email("revoked")
        joiner, _ = await _sign_in(client, address, "Revoked Ltd")
        body = await _invite(client, owner, address)
        token = await _plaintext_token(db, client, body)

        dropped = await client.delete(f"/org/{slug}/invitations/{body['id']}", headers=headers)
        assert dropped.status_code == 204
        assert (await client.get(f"/invitations/{token}")).status_code == 410
        retried = await client.post(f"/invitations/{token}/accept", headers=joiner)
        assert retried.status_code == 410

    async def test_an_expired_invitation_is_gone(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        body = await _invite(client, owner, _email("stale"))
        token = await _plaintext_token(db, client, body)

        row = await db.get(Invitation, uuid.UUID(body["id"]))
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await db.commit()

        assert (await client.get(f"/invitations/{token}")).status_code == 410

    async def test_an_unknown_token_is_404(self, client: AsyncClient) -> None:
        assert (await client.get("/invitations/not-a-real-token")).status_code == 404

    async def test_the_preview_names_the_organisation_and_nothing_else(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        """The token is a capability to *join*, not a capability to read."""
        headers, slug = owner
        body = await _invite(client, owner, _email("peek"), role="admin")
        token = await _plaintext_token(db, client, body)

        preview = (await client.get(f"/invitations/{token}")).json()
        assert preview == {
            "organisation": "Apollo Care Fixtures",
            "organisation_slug": slug,
            "tenant_type": "employer",
            "role": "admin",
        }
        inviter = (await client.get("/auth/me", headers=headers)).json()["email"]
        assert inviter not in str(preview)

    async def test_revoking_an_accepted_invitation_leaves_the_membership(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        """Otherwise revocation would be a way past the last-owner guard."""
        headers, slug = owner
        address = _email("kept")
        body = await _invite(client, owner, address)
        joiner = await _accept_as_new_account(client, db, body, address)

        refused = await client.delete(f"/org/{slug}/invitations/{body['id']}", headers=headers)
        assert refused.status_code == 409
        me = (await client.get("/auth/me", headers=joiner)).json()
        assert {m["tenant"]["slug"] for m in me["memberships"]} == {slug}


class TestTheLoadBearing401:
    async def test_an_unknown_address_with_no_invitation_still_gets_401(
        self, client: AsyncClient
    ) -> None:
        """**This is the test the whole sprint is written around.**

        `verify_email_and_sign_in` gained an account-creating branch, and its
        refusal of an unknown address is what stops a valid code minting a
        blank organisation. A code alone must never be enough.
        """
        address = _email("nobody")
        requested = await client.post("/auth/email/otp/request", json={"email": address})
        code = requested.json()["debug_code"]

        refused = await client.post(
            "/auth/email/otp/verify",
            json={"email": address, "code": code, "consent_version": CONSENT},
        )
        assert refused.status_code == 401

    async def test_an_invited_address_without_consent_gets_428_not_an_account(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        address = _email("noconsent")
        body = await _invite(client, owner, address)
        token = await _plaintext_token(db, client, body)
        claimed = await client.post(f"/invitations/{token}/claim")
        code = claimed.json()["debug_code"]

        refused = await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
        assert refused.status_code == 428
        assert await db.scalar(select(User).where(User.email == address)) is None


class TestMembers:
    async def test_every_member_can_see_who_works_here(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        owner_headers, slug = owner
        address = _email("colleague")
        member_headers = await _accept_as_new_account(
            client, db, await _invite(client, owner, address), address
        )

        listed = (await client.get(f"/org/{slug}/members", headers=member_headers)).json()
        assert {m["role"] for m in listed} == {"owner", "member"}
        assert [m["role"] for m in listed] == ["owner", "member"], "owners first"
        assert sum(1 for m in listed if m["is_you"]) == 1
        # Colleagues, not candidates: an address to reach them by, no phone.
        assert all("phone" not in m for m in listed)

    async def test_a_member_cannot_change_roles_or_remove(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        owner_headers, slug = owner
        address = _email("powerless")
        member_headers = await _accept_as_new_account(
            client, db, await _invite(client, owner, address), address
        )
        target = (await client.get("/auth/me", headers=owner_headers)).json()["id"]

        assert (
            await client.patch(
                f"/org/{slug}/members/{target}", headers=member_headers, json={"role": "member"}
            )
        ).status_code == 403
        assert (
            await client.delete(f"/org/{slug}/members/{target}", headers=member_headers)
        ).status_code == 403

    async def test_an_owner_promotes_and_removes(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        owner_headers, slug = owner
        address = _email("promoted")
        joiner = await _accept_as_new_account(
            client, db, await _invite(client, owner, address), address
        )
        joiner_id = (await client.get("/auth/me", headers=joiner)).json()["id"]

        promoted = await client.patch(
            f"/org/{slug}/members/{joiner_id}", headers=owner_headers, json={"role": "admin"}
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "admin"

        removed = await client.delete(f"/org/{slug}/members/{joiner_id}", headers=owner_headers)
        assert removed.status_code == 204
        me = (await client.get("/auth/me", headers=joiner)).json()
        assert slug not in {m["tenant"]["slug"] for m in me["memberships"]}


class TestTheLastOwner:
    """One question -- "would this leave nobody in charge?" -- asked in one
    service function and reached by three different routes. Three handlers
    asking it three times is three chances to ask it differently, which is
    exactly how Sprint 15's publishing guard went missing from three of eight
    writes."""

    async def test_the_last_owner_cannot_be_removed(
        self, client: AsyncClient, owner: tuple[dict[str, str], str]
    ) -> None:
        headers, slug = owner
        me = (await client.get("/auth/me", headers=headers)).json()["id"]
        refused = await client.delete(f"/org/{slug}/members/{me}", headers=headers)
        assert refused.status_code == 409

    async def test_the_last_owner_cannot_be_demoted(
        self, client: AsyncClient, owner: tuple[dict[str, str], str]
    ) -> None:
        headers, slug = owner
        me = (await client.get("/auth/me", headers=headers)).json()["id"]
        refused = await client.patch(
            f"/org/{slug}/members/{me}", headers=headers, json={"role": "admin"}
        )
        assert refused.status_code == 409

    async def test_the_last_owner_cannot_leave(
        self, client: AsyncClient, owner: tuple[dict[str, str], str]
    ) -> None:
        headers, slug = owner
        refused = await client.post(f"/org/{slug}/leave", headers=headers)
        assert refused.status_code == 409

    async def test_a_second_owner_makes_all_three_possible(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        owner_headers, slug = owner
        address = _email("successor")
        successor = await _accept_as_new_account(
            client, db, await _invite(client, owner, address, role="admin"), address
        )
        successor_id = (await client.get("/auth/me", headers=successor)).json()["id"]
        await client.patch(
            f"/org/{slug}/members/{successor_id}", headers=owner_headers, json={"role": "owner"}
        )

        left = await client.post(f"/org/{slug}/leave", headers=owner_headers)
        assert left.status_code == 204
        remaining = (await client.get(f"/org/{slug}/members", headers=successor)).json()
        assert [m["role"] for m in remaining] == ["owner"]

    async def test_a_member_may_leave_freely(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        _, slug = owner
        address = _email("leaver")
        joiner = await _accept_as_new_account(
            client, db, await _invite(client, owner, address), address
        )
        assert (await client.post(f"/org/{slug}/leave", headers=joiner)).status_code == 204
        assert (await client.get(f"/org/{slug}/members", headers=joiner)).status_code == 404


class TestTheOrganisationSurvivesItsOwner:
    """The bug this sprint exists to close.

    Until now the 409 in `privacy/service.py` was **unreachable**: it needs a
    second owner, and no second member could exist. So a sole owner deleting
    their account hard-deleted the tenant, its vacancies and every application
    to them, telling nobody -- while the guard's own message told them to do
    something the product could not do.
    """

    async def test_an_owner_with_a_colleague_and_no_successor_is_refused(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        owner_headers, slug = owner
        address = _email("orphan")
        await _accept_as_new_account(client, db, await _invite(client, owner, address), address)

        refused = await client.delete("/me/account", headers=owner_headers)
        assert refused.status_code == 409
        assert "owner" in refused.json()["detail"].lower()
        assert await db.scalar(select(Tenant).where(Tenant.slug == slug)) is not None

    async def test_with_a_second_owner_the_deletion_succeeds_and_the_org_survives(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        """The test that was impossible to write before this sprint."""
        owner_headers, slug = owner
        address = _email("heir")
        heir = await _accept_as_new_account(
            client, db, await _invite(client, owner, address, role="admin"), address
        )
        heir_id = (await client.get("/auth/me", headers=heir)).json()["id"]
        await client.patch(
            f"/org/{slug}/members/{heir_id}", headers=owner_headers, json={"role": "owner"}
        )

        gone = await client.delete("/me/account", headers=owner_headers)
        assert gone.status_code == 204

        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None, "the organisation must outlive one of its owners"
        survivors = (await client.get(f"/org/{slug}/members", headers=heir)).json()
        assert [m["role"] for m in survivors] == ["owner"]

    async def test_erasure_takes_the_organisations_invitations(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Explicitly, not by cascade -- and an invitation is the one row in
        this product holding somebody else's address."""
        solo = await _sign_in(client, _email("solo"), "Solo Clinic")
        headers, slug = solo
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
        assert tenant is not None
        await _invite(client, solo, _email("never-accepted"))

        assert (await client.delete("/me/account", headers=headers)).status_code == 204
        left = await db.scalars(select(Invitation).where(Invitation.tenant_id == tenant.id))
        assert left.all() == []


class TestAnalytics:
    async def test_the_events_reach_the_table(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        """**This is the test that catches a forgotten CHECK migration.**

        `record()` swallows its own failures by contract, so a name added to
        `EVENT_NAMES` without widening `ck_analytics_event_name` produces no
        error anywhere -- only events that silently never appear.
        """
        from api.modules.analytics.models import AnalyticsEvent

        address = _email("measured")
        await _accept_as_new_account(client, db, await _invite(client, owner, address), address)
        names = set(
            (
                await db.scalars(
                    select(AnalyticsEvent.name).where(AnalyticsEvent.name.like("member_%"))
                )
            ).all()
        )
        assert {"member_invited", "member_invitation_accepted"} <= names

    async def test_no_event_names_a_person(
        self, client: AsyncClient, db: AsyncSession, owner: tuple[dict[str, str], str]
    ) -> None:
        from api.modules.analytics.models import AnalyticsEvent

        address = _email("private")
        await _invite(client, owner, address)
        rows = (
            await db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.name == "member_invited"))
        ).all()
        assert rows
        for row in rows:
            # The subject is the organisation, never the person invited: an
            # address is an identity, and this table carries none.
            assert row.subject_type == "tenant"
            assert address not in str(row.payload)


# --------------------------------------------------------------------- helpers


async def _plaintext_token(db: AsyncSession, client: AsyncClient, body: dict) -> str:
    """Recover a usable token for an invitation the API has created.

    There is no way to read one back -- the row keeps only an HMAC, which is
    the property worth having -- so the test writes a known token's hash onto
    the row instead. That exercises `invitation_for_token`'s real lookup rather
    than bypassing it.
    """
    from api.core.security import hash_secret

    token = f"test-token-{uuid.uuid4().hex}"
    row = await db.get(Invitation, uuid.UUID(body["id"]))
    assert row is not None
    row.token_hash = hash_secret(token)
    await db.commit()
    return token


async def _accept_as_new_account(
    client: AsyncClient, db: AsyncSession, body: dict, address: str
) -> dict[str, str]:
    """The stranger's path, end to end: claim, verify, account, membership."""
    token = await _plaintext_token(db, client, body)
    claimed = await client.post(f"/invitations/{token}/claim")
    assert claimed.status_code == 200, claimed.text
    assert "@" in claimed.json()["email_hint"]

    verified = await client.post(
        "/auth/email/otp/verify",
        json={
            "email": address,
            "code": claimed.json()["debug_code"],
            "consent_version": CONSENT,
        },
    )
    assert verified.status_code == 200, verified.text
    return {"authorization": f"Bearer {verified.json()['access_token']}"}
