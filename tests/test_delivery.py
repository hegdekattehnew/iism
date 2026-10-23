"""Sprint 97 (ADR-102, ADR-103, BL-18.15): delivering somebody else's course.

A partner asks, a seller approves (or the seller invites, which is its approval), either side ends
it, and **`authorises` is the question batches will ask**. What matters here: only the seller
approves, only a party can touch a row, every change tells the other side once in fixed words, the
state is derived from timestamps, and an organisation cannot be switched out of a capability from
under a standing arrangement.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics.models import AnalyticsEvent
from api.modules.delivery import CourseDeliveryAuthorisation as Arrangement
from api.modules.delivery import authorises, service
from api.modules.marketplace.models import Course
from api.modules.notifications.models import Notification
from tests.test_training_organisations import _register, _tenant

H = dict[str, str]


async def _seller(client: AsyncClient, name: str | None = None) -> tuple[H, str]:
    return await _register(
        client, name or f"Seller {uuid.uuid4().hex[:6]}", sells=True, delivers=False
    )


async def _partner(client: AsyncClient, name: str | None = None) -> tuple[H, str]:
    return await _register(
        client, name or f"Partner {uuid.uuid4().hex[:6]}", sells=False, delivers=True
    )


async def _course(client: AsyncClient, headers: H, org: str, title: str = "Welding basics") -> str:
    made = await client.post(f"/org/{org}/courses", headers=headers, json={"title": title})
    assert made.status_code == 201, made.text
    return made.json()["slug"]


async def _ask(client, headers, org, provider, course=None):
    return await client.post(
        f"/org/{org}/delivery/requests",
        headers=headers,
        json={"organisation_slug": provider, "course_slug": course},
    )


async def _invite(client, headers, org, partner, course=None):
    return await client.post(
        f"/org/{org}/delivery/invitations",
        headers=headers,
        json={"organisation_slug": partner, "course_slug": course},
    )


async def _act(client, headers, org, row, verb):
    return await client.post(f"/org/{org}/delivery/{row}/{verb}", headers=headers)


async def _notices(db: AsyncSession, org: str, template: str) -> list[Notification]:
    tenant = await _tenant(db, org)
    return list(
        (
            await db.scalars(
                select(Notification).where(
                    Notification.recipient_kind == "tenant",
                    Notification.recipient_id == tenant.id,
                    Notification.template == template,
                )
            )
        ).all()
    )


async def _course_row(db: AsyncSession, slug: str) -> Course:
    row = await db.scalar(select(Course).where(Course.slug == slug))
    assert row is not None
    return row


@pytest.fixture
async def world(client: AsyncClient):
    seller_h, seller = await _seller(client)
    partner_h, partner = await _partner(client)
    welding = await _course(client, seller_h, seller, "Welding basics")
    plumbing = await _course(client, seller_h, seller, "Plumbing basics")
    return seller_h, seller, partner_h, partner, welding, plumbing


# ----------------------------------------------------------------- asking and approving


async def test_a_partner_asks_and_the_seller_is_told_once_in_fixed_words(client, db, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    made = await _ask(client, partner_h, partner, seller, welding)
    assert made.status_code == 201, made.text
    body = made.json()
    assert (
        body["state"] == "requested"
        and body["side"] == "partner"
        and body["initiated_by"] == "partner"
    )
    assert body["other"]["slug"] == seller and body["course"]["slug"] == welding

    mail = await _notices(db, seller, "delivery_requested")
    assert len(mail) == 1
    assert set(mail[0].payload) == {"organisation", "path"}, "the notice carries a name and a link"
    assert mail[0].payload["path"] == f"/employer/{seller}/delivery"
    events = (
        await db.scalars(
            select(AnalyticsEvent.name).where(AnalyticsEvent.name == "delivery_requested")
        )
    ).all()
    assert events


async def test_nothing_is_authorised_until_the_seller_approves(client, db, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    course = await _course_row(db, welding)
    partner_id = (await _tenant(db, partner)).id
    assert await authorises(db, partner_id, course) is False

    approved = await _act(client, seller_h, seller, row, "approve")
    assert approved.status_code == 200 and approved.json()["state"] == "approved"
    assert approved.json()["side"] == "provider"
    assert await authorises(db, partner_id, course) is True
    assert len(await _notices(db, partner, "delivery_approved")) == 1


async def test_a_single_course_covers_that_course_only_and_all_covers_every_one(client, db, world):
    seller_h, seller, partner_h, partner, welding, plumbing = world
    one = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    await _act(client, seller_h, seller, one, "approve")
    partner_id = (await _tenant(db, partner)).id
    assert await authorises(db, partner_id, await _course_row(db, welding)) is True
    assert await authorises(db, partner_id, await _course_row(db, plumbing)) is False

    every = (await _ask(client, partner_h, partner, seller)).json()["id"]
    assert (await _act(client, seller_h, seller, every, "approve")).status_code == 200
    assert await authorises(db, partner_id, await _course_row(db, plumbing)) is True


async def test_an_organisation_always_delivers_its_own_course_with_no_row(client, db):
    headers, org = await _register(client, "Both Ways", sells=True, delivers=True)
    slug = await _course(client, headers, org)
    both_id = (await _tenant(db, org)).id
    assert await authorises(db, both_id, await _course_row(db, slug)) is True
    assert (await db.scalar(select(Arrangement.id))) is None


async def test_nobody_else_delivers_a_course_it_holds_no_arrangement_for(client, db, world):
    _, _, _, partner, welding, _ = world
    stranger_h, stranger = await _partner(client)
    assert (
        await authorises(db, (await _tenant(db, stranger)).id, await _course_row(db, welding))
        is False
    )


async def test_a_sellers_invitation_is_its_approval(client, db, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    made = await _invite(client, seller_h, seller, partner, welding)
    assert made.status_code == 201, made.text
    body = made.json()
    assert (
        body["state"] == "approved"
        and body["initiated_by"] == "provider"
        and body["side"] == "provider"
    )
    assert (
        await authorises(db, (await _tenant(db, partner)).id, await _course_row(db, welding))
        is True
    )
    assert len(await _notices(db, partner, "delivery_invited")) == 1
    # And the partner sees it, from its own side.
    mine = (await client.get(f"/org/{partner}/delivery", headers=partner_h)).json()
    assert [(r["side"], r["state"]) for r in mine["as_partner"]] == [("partner", "approved")]


# -------------------------------------------------------------------- ending


async def test_the_seller_declines_and_the_partner_is_told(client, db, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    declined = await _act(client, seller_h, seller, row, "decline")
    assert declined.status_code == 200
    body = declined.json()
    assert body["state"] == "declined" and body["ended_by_side"] == "provider"
    assert len(await _notices(db, partner, "delivery_declined")) == 1
    assert (await _act(client, seller_h, seller, row, "approve")).status_code == 409


async def test_the_partner_may_withdraw_its_own_request(client, db, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    withdrawn = await _act(client, partner_h, partner, row, "decline")
    assert (
        withdrawn.json()["state"] == "declined" and withdrawn.json()["ended_by_side"] == "partner"
    )
    assert len(await _notices(db, seller, "delivery_declined")) == 1


@pytest.mark.parametrize("by", ["seller", "partner"])
async def test_either_side_may_end_an_approved_arrangement(client, db, world, by):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _invite(client, seller_h, seller, partner, welding)).json()["id"]
    org, headers, other = (
        (seller, seller_h, partner) if by == "seller" else (partner, partner_h, seller)
    )
    ended = await _act(client, headers, org, row, "revoke")
    assert ended.status_code == 200
    assert ended.json()["state"] == "revoked" and ended.json()["ended_by_side"] == (
        "provider" if by == "seller" else "partner"
    )
    assert len(await _notices(db, other, "delivery_revoked")) == 1
    assert (
        await authorises(db, (await _tenant(db, partner)).id, await _course_row(db, welding))
        is False
    )


async def test_a_state_can_only_be_left_from_the_right_one(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    assert (await _act(client, seller_h, seller, row, "revoke")).status_code == 409, (
        "not approved yet"
    )
    await _act(client, seller_h, seller, row, "approve")
    assert (await _act(client, seller_h, seller, row, "decline")).status_code == 409, (
        "already approved"
    )
    assert (await _act(client, seller_h, seller, row, "approve")).status_code == 409, (
        "already approved"
    )
    await _act(client, seller_h, seller, row, "revoke")
    assert (await _act(client, partner_h, partner, row, "revoke")).status_code == 409, (
        "already ended"
    )


async def test_the_state_is_derived_from_the_timestamps(client, db, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    stored = await db.get(Arrangement, uuid.UUID(row))
    assert stored is not None and stored.state == "requested"
    assert not hasattr(Arrangement, "status")
    await _act(client, seller_h, seller, row, "approve")
    await db.refresh(stored)
    assert stored.state == "approved"
    await _act(client, partner_h, partner, row, "revoke")
    await db.refresh(stored)
    assert stored.state == "revoked"


# ----------------------------------------------------------------- who may do what


async def test_only_the_seller_approves(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    refused = await _act(client, partner_h, partner, row, "approve")
    assert refused.status_code == 403, "the partner is not a seller: the capability refuses"
    both_h, both = await _register(client, "Both", sells=True, delivers=True)
    # A seller that is not this row's seller cannot see it at all.
    assert (await _act(client, both_h, both, row, "approve")).status_code == 404


async def test_an_organisation_that_both_sells_and_delivers_cannot_approve_its_own_request(
    client, world
):
    """The capability lets it through; the row says it is the partner: only the seller approves."""
    seller_h, seller, *_ = world
    both_h, both = await _register(client, "Both Ways", sells=True, delivers=True)
    row = (await _ask(client, both_h, both, seller)).json()["id"]
    refused = await _act(client, both_h, both, row, "approve")
    assert refused.status_code == 403 and "sells the course" in refused.json()["detail"]
    assert (await _act(client, seller_h, seller, row, "approve")).status_code == 200


async def test_a_stranger_gets_the_404_of_a_row_that_does_not_exist(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    other_h, other = await _register(client, "Other", sells=True, delivers=True)
    for verb in ("approve", "decline", "revoke"):
        real = await _act(client, other_h, other, row, verb)
        absent = await _act(client, other_h, other, str(uuid.uuid4()), verb)
        assert real.status_code == absent.status_code == 404
        assert real.json() == absent.json()
    listed = (await client.get(f"/org/{other}/delivery", headers=other_h)).json()
    assert listed == {"as_partner": [], "as_provider": []}


async def test_the_capability_decides_which_side_an_organisation_may_start(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    assert (await _ask(client, seller_h, seller, partner)).status_code == 403, (
        "a seller does not deliver"
    )
    assert (await _invite(client, partner_h, partner, seller)).status_code == 403, (
        "a deliverer does not sell"
    )
    employer_h, employer = await _register(client, "An Employer", tenant_type="employer")
    assert (await client.get(f"/org/{employer}/delivery", headers=employer_h)).status_code == 403


async def test_a_plain_member_may_look_but_not_decide(client, db, world):
    from tests.test_invitations import _accept_as_new_account, _email

    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    address = _email("member")
    sent = await client.post(
        f"/org/{seller}/invitations", headers=seller_h, json={"email": address, "role": "member"}
    )
    member = await _accept_as_new_account(client, db, sent.json(), address)
    assert (await client.get(f"/org/{seller}/delivery", headers=member)).status_code == 200
    assert (await _act(client, member, seller, row, "approve")).status_code == 403
    assert (await _invite(client, member, seller, partner)).status_code == 403


async def test_a_centres_manager_has_no_arrangements(client, db, world, place):
    from tests.test_centre_staff import _centre, _manager

    headers, org = await _register(client, "Centre Owner", sells=False, delivers=True)
    centre = await _centre(client, headers, org, place)
    manager = await _manager(client, db, headers, org, centre)
    assert (await client.get(f"/org/{centre}/delivery", headers=manager)).status_code == 403


# ------------------------------------------------------------------ the counterparty


async def test_the_other_organisation_must_be_the_kind_asked_for_and_not_oneself(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    employer_h, employer = await _register(client, "An Employer", tenant_type="employer")
    missing = await _ask(client, partner_h, partner, "no-such-organisation")
    for slug in (employer, partner, "no-such-organisation"):
        refused = await _ask(client, partner_h, partner, slug)
        assert refused.status_code == 404 and refused.json() == missing.json(), slug
    # A deliverer-only organisation is not somebody to ask to deliver *its* courses.
    other_h, other = await _partner(client)
    assert (await _ask(client, partner_h, partner, other)).status_code == 404
    # And inviting needs a deliverer.
    assert (await _invite(client, seller_h, seller, seller)).status_code == 404
    other_seller_h, other_seller = await _seller(client)
    assert (await _invite(client, seller_h, seller, other_seller)).status_code == 404


async def test_the_course_must_be_the_sellers(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    other_h, other = await _seller(client)
    theirs = await _course(client, other_h, other, "Their course")
    refused = await _ask(client, partner_h, partner, seller, theirs)
    assert refused.status_code == 404
    assert (await _ask(client, partner_h, partner, seller, "no-such-course")).status_code == 404


# ----------------------------------------------------------------------- the limits


async def test_one_open_arrangement_per_scope_and_all_covers_each(client, world):
    seller_h, seller, partner_h, partner, welding, plumbing = world
    assert (await _ask(client, partner_h, partner, seller, welding)).status_code == 201
    assert (await _ask(client, partner_h, partner, seller, welding)).status_code == 409
    assert (await _ask(client, partner_h, partner, seller, plumbing)).status_code == 201
    assert (await _ask(client, partner_h, partner, seller)).status_code == 201, (
        "broadening is allowed"
    )
    assert (await _ask(client, partner_h, partner, seller)).status_code == 409


async def test_with_every_course_open_one_course_is_already_covered(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    assert (await _ask(client, partner_h, partner, seller)).status_code == 201
    covered = await _ask(client, partner_h, partner, seller, welding)
    assert covered.status_code == 409 and "already covered" in covered.json()["detail"]


async def test_an_ended_arrangement_can_be_asked_for_again(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    await _act(client, seller_h, seller, row, "decline")
    assert (await _ask(client, partner_h, partner, seller, welding)).status_code == 201


async def test_the_same_pair_cannot_ask_again_and_again_in_a_day(client, world, monkeypatch):
    monkeypatch.setattr(service, "MAX_ASKS_PER_PAIR_PER_DAY", 2)
    seller_h, seller, partner_h, partner, welding, _ = world
    for _ in range(2):
        row = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
        await _act(client, partner_h, partner, row, "decline")
    limited = await _ask(client, partner_h, partner, seller, welding)
    assert limited.status_code == 429 and limited.headers["retry-after"]


async def test_an_organisation_cannot_leave_many_requests_unanswered(client, world, monkeypatch):
    monkeypatch.setattr(service, "MAX_OPEN_REQUESTS", 2)
    _, _, partner_h, partner, _, _ = world
    for _ in range(2):
        other_h, other = await _seller(client)
        assert (await _ask(client, partner_h, partner, other)).status_code == 201
    last_h, last = await _seller(client)
    assert (await _ask(client, partner_h, partner, last)).status_code == 429


# ------------------------------------------------- capabilities cannot be pulled away


async def test_an_organisation_with_arrangements_cannot_switch_the_capability_off(client, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    both_h, both = await _register(client, "Both", sells=True, delivers=True)
    # As a deliverer: asks a seller.
    row = (await _ask(client, both_h, both, seller, welding)).json()["id"]
    off = await client.put(
        f"/org/{both}/capabilities", headers=both_h, json={"delivers_training": False}
    )
    assert off.status_code == 409 and "arrangements" in off.json()["detail"]
    await _act(client, both_h, both, row, "decline")
    assert (
        await client.put(
            f"/org/{both}/capabilities", headers=both_h, json={"delivers_training": False}
        )
    ).status_code == 200
    # As a seller: somebody holds one of its courses. (It delivers again, so it may stop selling
    # in principle; the standing arrangement is what refuses.)
    await client.put(f"/org/{both}/capabilities", headers=both_h, json={"delivers_training": True})
    other_h, other = await _partner(client)
    both_course = await _course(client, both_h, both)
    held = (await _invite(client, both_h, both, other, both_course)).json()["id"]
    stop = await client.put(
        f"/org/{both}/capabilities", headers=both_h, json={"sells_courses": False}
    )
    assert stop.status_code == 409 and "hold arrangements" in stop.json()["detail"]
    await _act(client, both_h, both, held, "revoke")
    assert (await client.get(f"/org/{both}", headers=both_h)).status_code == 200
    unpublished = await client.put(
        f"/org/{both}/capabilities", headers=both_h, json={"sells_courses": False}
    )
    assert unpublished.status_code == 200, unpublished.text


# ---------------------------------------------------------------------- reading


async def test_the_list_puts_open_arrangements_first_and_names_the_course(client, world):
    seller_h, seller, partner_h, partner, welding, plumbing = world
    old = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    await _act(client, seller_h, seller, old, "decline")
    await _ask(client, partner_h, partner, seller, plumbing)
    rows = (await client.get(f"/org/{partner}/delivery", headers=partner_h)).json()["as_partner"]
    assert [r["state"] for r in rows] == ["requested", "declined"]
    assert rows[0]["course"]["title"] == "Plumbing basics"
    assert rows[0]["other"]["name"].startswith("Seller")
    mine = (await client.get(f"/org/{seller}/delivery", headers=seller_h)).json()
    assert len(mine["as_provider"]) == 2 and mine["as_partner"] == []


async def test_search_finds_organisations_by_name_and_narrows_by_what_they_do(client, world):
    seller_h, seller, partner_h, partner, *_ = world
    name = (await client.get(f"/providers/{seller}")).json()["name"]
    found = (
        await client.get("/training-organisations", params={"q": name, "sells": "true"})
    ).json()
    assert [i["slug"] for i in found["items"]] == [seller] and found["total"] == 1
    none = (
        await client.get("/training-organisations", params={"q": name, "delivers": "true"})
    ).json()
    assert none["items"] == []
    partner_name = (await client.get(f"/providers/{partner}")).json()["name"]
    only_sellers = (
        await client.get("/training-organisations", params={"q": partner_name, "sells": "true"})
    ).json()
    assert only_sellers["items"] == [], "a deliverer that sells nothing is not a seller"
    everything = (
        await client.get("/training-organisations", params={"delivers": "true", "limit": 50})
    ).json()
    assert partner in [i["slug"] for i in everything["items"]]
    # Nobody is found by an employer's name: only training organisations are listed.
    emp_h, emp = await _register(client, "Zzyzx Employer", tenant_type="employer")
    assert (await client.get("/training-organisations", params={"q": "Zzyzx"})).json()[
        "items"
    ] == []
    # A search is text, not a pattern.
    assert (await client.get("/training-organisations", params={"q": "%"})).json()["items"] == []


async def test_the_public_page_lists_only_approved_unended_arrangements(client, world):
    seller_h, seller, partner_h, partner, welding, plumbing = world
    asked = (await _ask(client, partner_h, partner, seller, welding)).json()["id"]
    page = (await client.get(f"/providers/{partner}/delivery")).json()
    assert page["items"] == [], "a request nobody has answered is not a fact about anybody"

    await _act(client, seller_h, seller, asked, "approve")
    items = (await client.get(f"/providers/{partner}/delivery")).json()["items"]
    assert [(i["provider"]["slug"], i["course"]["slug"]) for i in items] == [(seller, welding)]

    every = (await _invite(client, seller_h, seller, partner)).json()["id"]
    items = (await client.get(f"/providers/{partner}/delivery")).json()["items"]
    assert sorted(i["course"] is None for i in items) == [False, True], (
        "one course, and all of them"
    )

    await _act(client, seller_h, seller, asked, "revoke")
    await _act(client, partner_h, partner, every, "revoke")
    assert (await client.get(f"/providers/{partner}/delivery")).json()["items"] == []


async def test_the_public_page_is_the_404_of_anything_that_is_not_a_training_organisation(client):
    employer_h, employer = await _register(client, "An Employer", tenant_type="employer")
    for slug in (employer, "no-such-organisation"):
        assert (await client.get(f"/providers/{slug}/delivery")).status_code == 404


# ---------------------------------------------------------------------- erasure


async def test_deleting_either_organisation_removes_its_arrangements(client, db, world):
    seller_h, seller, partner_h, partner, welding, _ = world
    await _invite(client, seller_h, seller, partner, welding)
    assert (await client.delete(f"/org/{partner}", headers=partner_h)).status_code == 204
    db.expire_all()
    assert (await db.scalar(select(Arrangement.id))) is None
    mine = (await client.get(f"/org/{seller}/delivery", headers=seller_h)).json()
    assert mine == {"as_partner": [], "as_provider": []}
