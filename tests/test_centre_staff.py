"""Sprint 96 (ADR-102, BL-18.4): the person who runs a training centre.

A manager is a membership on the **centre's own row**, brought in by the existing invitation flow by
the organisation that owns the centre. What matters here is what they can reach (their centre, and
nothing of the organisation), that the organisation alone decides who runs a centre, and that a
manager's departure, erasure or removal never touches the centre itself.
"""

import re
import uuid

import pytest
from sqlalchemy import select

from api.core.authorization import ROLE_PERMISSIONS, Permission
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import Membership, Tenant, centre_staff
from api.modules.identity.models import Invitation
from api.modules.notifications.models import Notification
from tests.test_centres import _body, _deliverer
from tests.test_invitations import _accept_as_new_account, _email, _plaintext_token
from tests.test_training_organisations import _register


async def _centre(client, headers, org, place, name="Hadapsar") -> str:
    made = await client.post(f"/org/{org}/centres", headers=headers, json=_body(name, place))
    assert made.status_code == 201, made.text
    return made.json()["slug"]


async def _invite(client, headers, org, centre, address=None):
    address = address or _email("mgr")
    response = await client.post(
        f"/org/{org}/centres/{centre}/managers", headers=headers, json={"email": address}
    )
    return response, address


async def _manager(client, db, headers, org, centre, address=None):
    """A centre manager, end to end: invited by the organisation, accepted as a new account."""
    response, address = await _invite(client, headers, org, centre, address)
    assert response.status_code == 201, response.text
    return await _accept_as_new_account(client, db, response.json(), address)


@pytest.fixture
async def setup(client, place):
    headers, org = await _deliverer(client)
    centre = await _centre(client, headers, org, place)
    return headers, org, centre


# ------------------------------------------------------------ the organisation brings one in


async def test_an_owner_asks_somebody_to_run_a_centre(client, db, setup):
    headers, org, centre = setup
    response, address = await _invite(client, headers, org, centre)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "manager" and body["state"] == "pending" and body["email"] == address
    assert "token" not in body

    row = await db.scalar(select(Invitation).where(Invitation.email == address))
    centre_row = await db.scalar(select(Tenant).where(Tenant.slug == centre))
    assert row is not None and centre_row is not None and row.tenant_id == centre_row.id

    mail = await db.scalar(
        select(Notification).where(
            Notification.recipient_kind == "invitation", Notification.recipient_id == row.id
        )
    )
    assert mail is not None and mail.template == "centre_manager_invitation"
    assert mail.payload["centre"] == "Hadapsar" and mail.payload["organisation"]
    assert mail.payload["path"].startswith("/invite/")


async def test_the_staff_list_shows_managers_and_invitations(client, db, setup):
    headers, org, centre = setup
    await _manager(client, db, headers, org, centre)
    await _invite(client, headers, org, centre)
    staff = (await client.get(f"/org/{org}/centres/{centre}/managers", headers=headers)).json()
    assert [m["role"] for m in staff["managers"]] == ["manager"]
    assert sorted(i["state"] for i in staff["invitations"]) == ["accepted", "pending"]


async def test_inviting_is_the_same_for_a_known_and_an_unknown_address(client, setup):
    headers, org, centre = setup
    known = _email("known")
    await _register(client, "Somebody Else", sells=True, delivers=False)  # a different account
    one, _ = await _invite(client, headers, org, centre, known)
    two, _ = await _invite(client, headers, org, centre)
    volatile = {"id", "email", "created_at", "expires_at"}
    assert {k: v for k, v in one.json().items() if k not in volatile} == {
        k: v for k, v in two.json().items() if k not in volatile
    }


async def test_a_duplicate_invitation_and_an_existing_manager_are_refused(client, db, setup):
    headers, org, centre = setup
    first, address = await _invite(client, headers, org, centre)
    again, _ = await _invite(client, headers, org, centre, address)
    assert first.status_code == 201 and again.status_code == 409
    taken = await _manager(client, db, headers, org, centre, _email("taken"))
    assert taken
    me = (await client.get("/auth/me", headers=taken)).json()
    later, _ = await _invite(client, headers, org, centre, me["email"])
    assert later.status_code == 409


async def test_a_closed_centre_cannot_be_given_a_manager(client, setup):
    headers, org, centre = setup
    await client.post(f"/org/{org}/centres/{centre}/close", headers=headers)
    refused, _ = await _invite(client, headers, org, centre)
    assert refused.status_code == 409


async def test_the_cap_counts_managers_and_open_invitations(client, setup, monkeypatch):
    monkeypatch.setattr(centre_staff, "MAX_MANAGERS", 2)
    headers, org, centre = setup
    assert (await _invite(client, headers, org, centre))[0].status_code == 201
    assert (await _invite(client, headers, org, centre))[0].status_code == 201
    assert (await _invite(client, headers, org, centre))[0].status_code == 409


async def test_the_organisations_own_team_route_cannot_offer_the_role(client, setup):
    headers, org, _ = setup
    response = await client.post(
        f"/org/{org}/invitations", headers=headers, json={"email": _email(), "role": "manager"}
    )
    assert response.status_code == 422


# ----------------------------------------------------------------------- who may do it


async def test_only_the_organisations_admins_and_owners_manage_a_centres_staff(client, db, setup):
    headers, org, centre = setup
    # A plain member of the organisation (no CENTRE_MANAGE).
    member_address = _email("member")
    sent = await client.post(
        f"/org/{org}/invitations", headers=headers, json={"email": member_address, "role": "member"}
    )
    member = await _accept_as_new_account(client, db, sent.json(), member_address)
    assert (await _invite(client, member, org, centre))[0].status_code == 403
    assert (
        await client.get(f"/org/{org}/centres/{centre}/managers", headers=member)
    ).status_code == 403

    # An admin may.
    admin_address = _email("admin")
    sent = await client.post(
        f"/org/{org}/invitations", headers=headers, json={"email": admin_address, "role": "admin"}
    )
    admin = await _accept_as_new_account(client, db, sent.json(), admin_address)
    assert (await _invite(client, admin, org, centre))[0].status_code == 201


async def test_a_stranger_and_another_organisation_get_the_404_of_a_missing_centre(client, setup):
    headers, org, centre = setup
    other_headers, other = await _deliverer(client)
    for who, slug in ((other_headers, org), (other_headers, other)):
        response = await client.get(f"/org/{slug}/centres/{centre}/managers", headers=who)
        assert response.status_code == 404
    missing = await client.get(
        f"/org/{other}/centres/no-such-centre/managers", headers=other_headers
    )
    real = await client.get(f"/org/{other}/centres/{centre}/managers", headers=other_headers)
    assert missing.json() == real.json()
    posted, _ = await _invite(client, other_headers, other, centre)
    assert posted.status_code == 404


async def test_a_seller_only_organisation_has_no_centre_staff(client, setup):
    _, _, centre = setup
    seller, org = await _register(client, "Seller", sells=True, delivers=False)
    assert (await _invite(client, seller, org, centre))[0].status_code == 403


# ------------------------------------------------------------------- what a manager reaches


async def test_a_manager_sees_their_centre_and_whose_it_is(client, db, setup):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)

    me = (await client.get("/auth/me", headers=manager)).json()
    held = [m for m in me["memberships"] if m["tenant"]["slug"] == centre]
    assert len(held) == 1 and held[0]["role"] == "manager"
    assert held[0]["tenant"]["tenant_type"] == "training_centre"

    mine = (await client.get(f"/org/{centre}/centre", headers=manager)).json()
    assert mine["name"] == "Hadapsar" and mine["organisation_slug"] == org and mine["organisation"]
    # Nothing else of the organisation travels with it.
    assert set(mine) == {
        "slug", "name", "address", "location_state", "location_district", "place_resolved",
        "status", "closed_at", "is_verified", "created_at", "organisation", "organisation_slug",
    }  # fmt: skip


async def test_a_manager_keeps_their_centres_details_true(client, db, setup, place):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)
    done = await client.put(
        f"/org/{centre}/centre", headers=manager, json=_body("Hadapsar East", place, "9 New Road")
    )
    assert done.status_code == 200 and done.json()["name"] == "Hadapsar East"
    # The organisation sees the same record.
    theirs = (await client.get(f"/org/{org}/centres/{centre}", headers=headers)).json()
    assert theirs["address"] == "9 New Road"


async def test_a_managers_edit_of_a_checked_address_takes_the_mark_away(client, db, setup, place):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)
    row = await db.scalar(select(Tenant).where(Tenant.slug == centre))
    assert row is not None
    owner_id = await db.scalar(
        select(Membership.user_id).where(Membership.tenant_id == row.parent_id)
    )
    from datetime import UTC, datetime

    row.verified_at = datetime.now(UTC)
    row.verified_by = owner_id
    row.verification_note = "Seen on site"
    await db.commit()
    moved = await client.put(
        f"/org/{centre}/centre", headers=manager, json=_body("Hadapsar", place, "Somewhere else")
    )
    assert moved.status_code == 200 and moved.json()["is_verified"] is False


async def test_a_manager_cannot_edit_a_closed_centre(client, db, setup, place):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)
    await client.post(f"/org/{org}/centres/{centre}/close", headers=headers)
    refused = await client.put(
        f"/org/{centre}/centre", headers=manager, json=_body("Hadapsar", place)
    )
    assert refused.status_code == 409
    assert (await client.get(f"/org/{centre}/centre", headers=manager)).json()["status"] == "closed"


async def test_a_managers_reach_is_their_centre_alone(client, db, setup, place):
    """Every route under an organisation's slug, asked as a manager, with their centre's slug.

    Only the four things a manager is meant to do succeed; everything else is a refusal. The list is
    read off the route table, so a route added next sprint is judged without anybody remembering to
    add it here.
    """
    from api.main import app

    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)

    def routes(items):
        for route in items:
            if hasattr(route, "original_router"):
                yield from routes(route.original_router.routes)
            elif hasattr(route, "methods"):
                yield route

    # What a manager may do in their own slug. (`leave` is tested on its own: it is destructive.)
    allowed = {
        ("GET", "/org/{org_slug}/members"),
        ("GET", "/org/{org_slug}/centre"),
        ("PUT", "/org/{org_slug}/centre"),
        # Sprints 98 and 99: the batches of their own centre, to read and to plan (a body-less POST
        # and PUT are a 422: they were let in, and then refused for the empty body), the figures
        # for their home, and the courses their organisation lets them plan from. A file of
        # batches names a centre on every row and the seller's counts are the seller's, so
        # neither is in this list.
        ("GET", "/org/{org_slug}/batches"),
        ("POST", "/org/{org_slug}/batches"),
        ("GET", "/org/{org_slug}/batches/courses"),
        ("GET", "/org/{org_slug}/batches/overview"),
        ("PUT", "/org/{org_slug}/batches/{batch_id}"),
        ("POST", "/org/{org_slug}/leave"),
    }
    seen = 0
    leaks: list[tuple[str, str, int]] = []
    for route in routes(app.routes):
        if not route.path.startswith("/org/{org_slug}"):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            if (method, route.path) == ("POST", "/org/{org_slug}/leave"):
                continue
            path = re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), route.path)
            path = path.replace(path.split("/")[2], centre, 1)
            seen += 1
            response = await client.request(method, path, headers=manager, content=b"")
            if (method, route.path) in allowed:
                assert response.status_code in (200, 422), (
                    method,
                    route.path,
                    response.status_code,
                )
            elif response.status_code not in (403, 404):
                leaks.append((method, route.path, response.status_code))
    assert leaks == [], leaks
    assert seen > 30, "the sweep found the route table"


async def test_a_manager_cannot_reach_a_sibling_centre_or_the_organisation(
    client, db, setup, place
):
    headers, org, centre = setup
    sibling = await _centre(client, headers, org, place, "Other Centre")
    manager = await _manager(client, db, headers, org, centre)
    for slug in (sibling, org):
        assert (await client.get(f"/org/{slug}/centre", headers=manager)).status_code == 404
        assert (await client.get(f"/org/{slug}", headers=manager)).status_code == 404
    assert (await client.get(f"/org/{org}/centres", headers=manager)).status_code == 404


async def test_an_organisations_owner_cannot_use_a_centres_own_door(client, setup):
    headers, org, centre = setup
    assert (await client.get(f"/org/{centre}/centre", headers=headers)).status_code == 404
    assert (await client.get(f"/org/{org}/centre", headers=headers)).status_code == 403


def test_no_organisation_role_holds_a_managers_permissions_and_the_manager_holds_no_organisations():
    managed = {Permission.MANAGED_CENTRE_READ, Permission.MANAGED_CENTRE_EDIT}
    for role in ("owner", "admin", "member"):
        assert not (ROLE_PERMISSIONS[role] & managed), role
    manager = ROLE_PERMISSIONS["manager"]
    assert managed <= manager
    assert manager == {
        Permission.MEMBER_READ,
        Permission.MANAGED_CENTRE_READ,
        Permission.MANAGED_CENTRE_EDIT,
        # Sprints 98 and 99: they read and plan their own centre's batches.
        Permission.BATCH_READ,
        Permission.BATCH_MANAGE,
    }
    # ...and nothing about files of batches (a centre per row), arrangements or the team.
    assert Permission.CENTRE_MANAGE not in manager and Permission.DELIVERY_READ not in manager


# -------------------------------------------------------------------- taking one out


async def test_removing_a_manager_ends_their_access_and_leaves_the_centre(client, db, setup):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)
    staff = (await client.get(f"/org/{org}/centres/{centre}/managers", headers=headers)).json()
    user_id = staff["managers"][0]["user_id"]
    gone = await client.delete(f"/org/{org}/centres/{centre}/managers/{user_id}", headers=headers)
    assert gone.status_code == 204
    assert (await client.get(f"/org/{centre}/centre", headers=manager)).status_code == 404
    assert (await client.get(f"/org/{org}/centres/{centre}", headers=headers)).status_code == 200
    again = await client.delete(f"/org/{org}/centres/{centre}/managers/{user_id}", headers=headers)
    assert again.status_code == 404
    events = (
        await db.scalars(select(AnalyticsEvent.name).where(AnalyticsEvent.name == "member_removed"))
    ).all()
    assert events


async def test_only_a_manager_can_be_removed_this_way(client, db, setup):
    headers, org, centre = setup
    owner_id = (await client.get("/auth/me", headers=headers)).json()["id"]
    refused = await client.delete(
        f"/org/{org}/centres/{centre}/managers/{owner_id}", headers=headers
    )
    assert refused.status_code == 404
    still = await client.get(f"/org/{org}/members", headers=headers)
    assert any(m["user_id"] == owner_id for m in still.json())


async def test_an_invitation_can_be_withdrawn_until_it_is_accepted(client, db, setup):
    headers, org, centre = setup
    sent, _ = await _invite(client, headers, org, centre)
    invitation = sent.json()["id"]
    withdrawn = await client.delete(
        f"/org/{org}/centres/{centre}/managers/invitations/{invitation}", headers=headers
    )
    assert withdrawn.status_code == 204
    staff = (await client.get(f"/org/{org}/centres/{centre}/managers", headers=headers)).json()
    assert [i["state"] for i in staff["invitations"]] == ["revoked"]

    accepted = await _manager(client, db, headers, org, centre)
    assert accepted
    spent = [
        i
        for i in (
            await client.get(f"/org/{org}/centres/{centre}/managers", headers=headers)
        ).json()["invitations"]
        if i["state"] == "accepted"
    ][0]["id"]
    refused = await client.delete(
        f"/org/{org}/centres/{centre}/managers/invitations/{spent}", headers=headers
    )
    assert refused.status_code == 409


async def test_a_manager_may_leave(client, db, setup):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)
    assert (await client.post(f"/org/{centre}/leave", headers=manager)).status_code == 204
    assert (await client.get(f"/org/{centre}/centre", headers=manager)).status_code == 404
    assert (await client.get(f"/org/{org}/centres/{centre}", headers=headers)).status_code == 200


# ---------------------------------------------------------------- the invitation's page


async def test_the_invitation_page_names_the_centre_and_its_organisation(client, db, setup):
    headers, org, centre = setup
    sent, _ = await _invite(client, headers, org, centre)
    token = await _plaintext_token(db, client, sent.json())
    preview = (await client.get(f"/invitations/{token}")).json()
    assert preview["tenant_type"] == "training_centre" and preview["role"] == "manager"
    assert preview["organisation"] == "Hadapsar" and preview["centre_of"]


# ---------------------------------------------------------------------- erasure


async def test_a_sole_managers_erasure_leaves_the_centre_alone(client, db, setup):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)
    preview = (await client.get("/me/account/deletion", headers=manager)).json()
    assert preview["organisations_deleted"] == [] and preview["blocked_by"] == []
    gone = await client.delete("/me/account", headers=manager)
    assert gone.status_code in (200, 204), gone.text
    assert (await client.get(f"/org/{org}/centres/{centre}", headers=headers)).status_code == 200


# ------------------------------------------------------------- what a centre does not count as


async def test_managing_a_centre_does_not_stop_you_creating_an_organisation_of_that_name(
    client, db, setup
):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)
    made = await client.post(
        "/me/organisations",
        headers=manager,
        json={
            "organisation_name": "Hadapsar",
            "tenant_type": "employer",
            "consent_version": CONSENT,
        },
    )
    assert made.status_code == 201, made.text


async def test_deleting_the_organisation_takes_the_centre_and_its_managers_memberships(
    client, db, setup
):
    headers, org, centre = setup
    manager = await _manager(client, db, headers, org, centre)
    await _invite(client, headers, org, centre)
    centre_row = await db.scalar(select(Tenant).where(Tenant.slug == centre))
    assert centre_row is not None
    centre_id = centre_row.id
    assert (await client.delete(f"/org/{org}", headers=headers)).status_code == 204
    db.expire_all()
    assert await db.scalar(select(Tenant.id).where(Tenant.id == centre_id)) is None
    left = await db.scalar(select(Membership.id).where(Membership.tenant_id == centre_id))
    assert left is None
    waiting = await db.scalar(select(Invitation.id).where(Invitation.tenant_id == centre_id))
    assert waiting is None
    # The manager is a person with an account; the account is not the centre's to take.
    assert (await client.get("/auth/me", headers=manager)).status_code == 200
