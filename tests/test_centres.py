"""Sprint 95 (ADR-102): an organisation that delivers training calls out its centres.

A centre is a child tenant with no membership of its own: the parent's owner and admin reach it
through the parent's slug, and anybody else gets the 404 a slug that does not exist would get.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from api.core.authorization import capability_for
from api.modules.analytics.models import AnalyticsEvent
from api.modules.centres import service
from api.modules.identity import Tenant
from api.modules.operations.models import TenantVerificationEvent
from tests.test_training_organisations import _register, _tenant


def _body(name: str, place: tuple[str, str], address: str | None = "12 Main Road") -> dict:
    return {"name": name, "address": address, "state": place[0], "district": place[1]}


async def _deliverer(client: AsyncClient) -> tuple[dict[str, str], str]:
    return await _register(client, f"Deliver {uuid.uuid4().hex[:6]}", sells=False, delivers=True)


async def test_an_owner_creates_lists_and_edits_a_centre(client, place):
    headers, org = await _deliverer(client)
    created = await client.post(
        f"/org/{org}/centres", headers=headers, json=_body("Hadapsar", place)
    )
    assert created.status_code == 201, created.text
    centre = created.json()
    assert centre["status"] == "active"
    assert centre["place_resolved"] is True
    assert centre["is_verified"] is False

    listed = (await client.get(f"/org/{org}/centres", headers=headers)).json()
    assert listed["total"] == 1 and listed["active"] == 1
    assert listed["items"][0]["slug"] == centre["slug"]

    edited = await client.put(
        f"/org/{org}/centres/{centre['slug']}",
        headers=headers,
        json=_body("Hadapsar East", place),
    )
    assert edited.status_code == 200 and edited.json()["name"] == "Hadapsar East"


async def test_an_unresolvable_place_is_kept_as_written_and_says_so(client, place):
    headers, org = await _deliverer(client)
    made = await client.post(
        f"/org/{org}/centres",
        headers=headers,
        json={"name": "Nowhere", "state": "Atlantis", "district": "Lemuria"},
    )
    assert made.status_code == 201
    body = made.json()
    assert body["place_resolved"] is False
    assert body["location_district"] == "Lemuria"


async def test_a_name_is_unique_within_the_organisation_closed_ones_included(client, place):
    headers, org = await _deliverer(client)
    first = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Pune Centre", place))
    ).json()
    again = await client.post(
        f"/org/{org}/centres", headers=headers, json=_body("pune centre.", place)
    )
    assert again.status_code == 409
    assert first["slug"] in again.json()["detail"]
    await client.post(f"/org/{org}/centres/{first['slug']}/close", headers=headers)
    still = await client.post(
        f"/org/{org}/centres", headers=headers, json=_body("Pune Centre", place)
    )
    assert still.status_code == 409, "a closed centre is reopened, not duplicated"


async def test_two_organisations_may_use_the_same_centre_name(client, place):
    a_headers, a = await _deliverer(client)
    b_headers, b = await _deliverer(client)
    one = await client.post(f"/org/{a}/centres", headers=a_headers, json=_body("Main", place))
    two = await client.post(f"/org/{b}/centres", headers=b_headers, json=_body("Main", place))
    assert one.status_code == two.status_code == 201
    assert one.json()["slug"] != two.json()["slug"]


async def test_closing_and_reopening(client, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Closer", place))
    ).json()["slug"]
    closed = (await client.post(f"/org/{org}/centres/{slug}/close", headers=headers)).json()
    assert closed["status"] == "closed" and closed["closed_at"]
    listed = (await client.get(f"/org/{org}/centres", headers=headers)).json()
    assert listed["total"] == 1 and listed["active"] == 0
    reopened = (await client.post(f"/org/{org}/centres/{slug}/reopen", headers=headers)).json()
    assert reopened["status"] == "active" and reopened["closed_at"] is None


async def test_a_seller_only_organisation_has_no_centres(client, place):
    headers, org = await _register(client, "Seller Only", sells=True, delivers=False)
    assert (await client.get(f"/org/{org}/centres", headers=headers)).status_code == 403
    made = await client.post(f"/org/{org}/centres", headers=headers, json=_body("X1", place))
    assert made.status_code == 403


async def test_an_employer_has_no_centres(client, place):
    headers, org = await _register(client, "An Employer", tenant_type="employer")
    assert (await client.get(f"/org/{org}/centres", headers=headers)).status_code == 403


async def test_a_stranger_gets_the_404_of_a_slug_that_does_not_exist(client, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Private", place))
    ).json()["slug"]
    stranger, _ = await _deliverer(client)
    real = await client.get(f"/org/{org}/centres/{slug}", headers=stranger)
    absent = await client.get(
        f"/org/no-such-org-{uuid.uuid4().hex[:6]}/centres/{slug}", headers=stranger
    )
    assert real.status_code == absent.status_code == 404
    assert real.json() == absent.json()


async def test_another_organisations_centre_is_not_reachable_through_your_own_slug(client, place):
    a_headers, a = await _deliverer(client)
    b_headers, b = await _deliverer(client)
    theirs = (
        await client.post(f"/org/{b}/centres", headers=b_headers, json=_body("Theirs", place))
    ).json()["slug"]
    for verb, suffix in (("get", ""), ("post", "/close"), ("post", "/reopen")):
        response = await getattr(client, verb)(
            f"/org/{a}/centres/{theirs}{suffix}", headers=a_headers
        )
        assert response.status_code == 404, (verb, suffix)
    put = await client.put(
        f"/org/{a}/centres/{theirs}", headers=a_headers, json=_body("Taken", place)
    )
    assert put.status_code == 404
    still = await client.get(f"/org/{b}/centres/{theirs}", headers=b_headers)
    assert still.json()["name"] == "Theirs"


async def test_a_centre_slug_is_not_an_organisation_you_can_act_in(client, db, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Door", place))
    ).json()["slug"]
    assert (await client.get(f"/org/{slug}/centres", headers=headers)).status_code == 404
    centre = await _tenant(db, slug)
    assert capability_for(centre, "batch") is True
    for capability in ("job", "course", "centre"):
        assert capability_for(centre, capability) is False


async def test_a_checked_address_that_changes_loses_its_mark(client, db, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Checked", place))
    ).json()["slug"]
    centre = await _tenant(db, slug)
    owner = await db.scalar(select(Tenant.id).where(Tenant.slug == org))
    assert owner is not None
    # An operator checked it (the verification columns carry their own CHECK).
    from api.modules.identity.models import Membership

    user_id = await db.scalar(select(Membership.user_id).where(Membership.tenant_id == owner))
    centre.verified_at = service.datetime.now(service.UTC)
    centre.verified_by = user_id
    centre.verification_note = "Visited the address on site"
    await db.commit()

    same_but_name = await client.put(
        f"/org/{org}/centres/{slug}", headers=headers, json=_body("Checked Renamed", place)
    )
    assert same_but_name.json()["is_verified"] is True, "a new name does not unmark an address"

    moved = await client.put(
        f"/org/{org}/centres/{slug}",
        headers=headers,
        json=_body("Checked Renamed", place, address="99 Another Road"),
    )
    assert moved.status_code == 200 and moved.json()["is_verified"] is False
    events = (
        await db.scalars(
            select(TenantVerificationEvent).where(TenantVerificationEvent.tenant_id == centre.id)
        )
    ).all()
    assert [e.decision for e in events] == ["revoked"]


async def test_creating_and_closing_are_measured(client, db, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Measured", place))
    ).json()["slug"]
    await client.post(f"/org/{org}/centres/{slug}/close", headers=headers)
    names = (
        await db.scalars(
            select(AnalyticsEvent.name).where(
                AnalyticsEvent.name.in_(["centre_created", "centre_closed"])
            )
        )
    ).all()
    assert "centre_created" in names and "centre_closed" in names


async def test_the_cap_refuses_the_next_centre(client, db, place, monkeypatch):
    monkeypatch.setattr(service, "MAX_CENTRES", 2)
    headers, org = await _deliverer(client)
    for n in range(2):
        ok = await client.post(
            f"/org/{org}/centres", headers=headers, json=_body(f"Cap {n}", place)
        )
        assert ok.status_code == 201
    over = await client.post(f"/org/{org}/centres", headers=headers, json=_body("Cap 3", place))
    assert over.status_code == 409


async def test_a_one_letter_name_is_refused_by_the_schema(client, place):
    headers, org = await _deliverer(client)
    response = await client.post(f"/org/{org}/centres", headers=headers, json=_body("A", place))
    assert response.status_code == 422


# ----------------------------------------------------------------------------- bulk upload


def _csv(*rows: tuple[str, str, str, str]) -> str:
    head = "name,address,state,district\n"
    return head + "".join(",".join(f'"{c}"' for c in r) + "\n" for r in rows)


async def _post_csv(client, url, headers, text):
    return await client.post(
        url, headers={**headers, "content-type": "text/csv"}, content=text.encode()
    )


async def test_bulk_check_writes_nothing_and_apply_creates(client, db, place):
    headers, org = await _deliverer(client)
    text = _csv(
        ("North", "1 Road", place[0], place[1]),
        ("South", "", place[0], place[1]),
        ("North", "2 Road", place[0], place[1]),
        ("Lost", "", "Atlantis", "Lemuria"),
        ("X", "", place[0], place[1]),
    )
    checked = (await _post_csv(client, f"/org/{org}/centres/bulk/check", headers, text)).json()
    assert checked["applied"] is False
    statuses = {r["row"]: r["status"] for r in checked["rows"]}
    assert statuses == {2: "ok", 3: "ok", 4: "error", 5: "warning", 6: "error"}
    assert checked["errors_csv"] and "error" in checked["errors_csv"].splitlines()[0]
    assert (await client.get(f"/org/{org}/centres", headers=headers)).json()["total"] == 0

    applied = (await _post_csv(client, f"/org/{org}/centres/bulk/apply", headers, text)).json()
    assert applied["created"] == 3
    assert (await client.get(f"/org/{org}/centres", headers=headers)).json()["total"] == 3

    again = (await _post_csv(client, f"/org/{org}/centres/bulk/apply", headers, text)).json()
    assert again["created"] == 0
    assert {r["status"] for r in again["rows"] if r["name"] in ("North", "South")} >= {"skip"}


async def test_bulk_respects_the_cap_in_check_and_apply(client, place, monkeypatch):
    monkeypatch.setattr(service, "MAX_CENTRES", 2)
    headers, org = await _deliverer(client)
    text = _csv(*[(f"Row {n}", "", place[0], place[1]) for n in range(4)])
    checked = (await _post_csv(client, f"/org/{org}/centres/bulk/check", headers, text)).json()
    applied = (await _post_csv(client, f"/org/{org}/centres/bulk/apply", headers, text)).json()
    assert checked["errors"] == applied["errors"] == 2
    assert applied["created"] == 2


async def test_bulk_refuses_a_file_that_is_not_a_centre_file(client):
    headers, org = await _deliverer(client)
    bad = await _post_csv(
        client, f"/org/{org}/centres/bulk/check", headers, "title,district\nx,y\n"
    )
    assert bad.status_code == 422


async def test_bulk_is_not_read_as_a_centre_slug(client, place):
    headers, org = await _deliverer(client)
    template = await client.get(f"/org/{org}/centres/bulk/template", headers=headers)
    assert template.status_code == 200 and template.text.startswith("name,address,state,district")


# ------------------------------------------------- stopping delivery, deleting, the public page


async def test_an_organisation_cannot_stop_delivering_while_a_centre_is_open(client, place):
    headers, org = await _register(client, "Both Ways", sells=True, delivers=True)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Held", place))
    ).json()["slug"]
    refused = await client.put(
        f"/org/{org}/capabilities", headers=headers, json={"delivers_training": False}
    )
    assert refused.status_code == 409 and "centres" in refused.json()["detail"]
    await client.post(f"/org/{org}/centres/{slug}/close", headers=headers)
    allowed = await client.put(
        f"/org/{org}/capabilities", headers=headers, json={"delivers_training": False}
    )
    assert allowed.status_code == 200, allowed.text
    # And with delivery off, even a closed centre cannot be brought back from the side.
    reopened = await client.post(f"/org/{org}/centres/{slug}/reopen", headers=headers)
    assert reopened.status_code == 403


async def test_the_preview_counts_centres_and_deleting_the_organisation_removes_them(
    client, db, place
):
    headers, org = await _deliverer(client)
    slugs = []
    for name in ("One", "Two"):
        made = await client.post(f"/org/{org}/centres", headers=headers, json=_body(name, place))
        slugs.append(made.json()["slug"])
    preview = (await client.get(f"/org/{org}/deletion", headers=headers)).json()
    assert preview["centres"] == 2
    account = (await client.get("/me/account/deletion", headers=headers)).json()
    fates = account["organisations_deleted"] + account["blocked_by"]
    assert [f["centres"] for f in fates if f["slug"] == org] == [2]

    assert (await client.delete(f"/org/{org}", headers=headers)).status_code == 204
    gone = (await db.scalars(select(Tenant.slug).where(Tenant.slug.in_([org, *slugs])))).all()
    assert gone == []


async def test_the_public_page_lists_open_centres_with_their_own_mark(client, db, place):
    headers, org = await _register(client, "Public Both", sells=True, delivers=True)
    open_slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Open One", place))
    ).json()["slug"]
    shut = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Shut One", place))
    ).json()["slug"]
    await client.post(f"/org/{org}/centres/{shut}/close", headers=headers)

    page = (await client.get(f"/providers/{org}")).json()
    assert [c["slug"] for c in page["centres"]] == [open_slug]
    assert page["centres"][0]["is_verified"] is False
    assert "closed_at" not in page["centres"][0]


async def test_a_centre_has_no_public_page_of_its_own(client, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Hidden", place))
    ).json()["slug"]
    assert (await client.get(f"/providers/{slug}")).status_code == 404


# ------------------------------------------------------------------- the operator's queue


async def _staff(client, db):
    from tests.test_operations import _operator

    return await _operator(client, db)


async def test_a_centre_is_in_the_queue_with_its_organisation_and_place(client, db, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Queued", place))
    ).json()["slug"]
    operator = await _staff(client, db)

    queue = (
        await client.get("/ops/organisations", headers=operator, params={"kind": "training_centre"})
    ).json()
    row = next(r for r in queue["items"] if r["slug"] == slug)
    assert row["tenant_type"] == "training_centre"
    assert row["parent_slug"] == org and row["parent_name"]
    assert row["district"] == place[1] and row["address"] == "12 Main Road"
    assert all(r["tenant_type"] == "training_centre" for r in queue["items"])

    everything = (await client.get("/ops/organisations", headers=operator)).json()
    dashboard = (await client.get("/ops/dashboard", headers=operator)).json()
    assert everything["total"] == dashboard["unverified_organisations"], "tile == queue"
    searched = (
        await client.get("/ops/organisations", headers=operator, params={"q": place[1][:9]})
    ).json()
    assert slug in [r["slug"] for r in searched["items"]]


async def test_a_closed_centre_leaves_the_queue(client, db, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Leaving", place))
    ).json()["slug"]
    operator = await _staff(client, db)
    await client.post(f"/org/{org}/centres/{slug}/close", headers=headers)
    queue = (
        await client.get("/ops/organisations", headers=operator, params={"kind": "training_centre"})
    ).json()
    assert slug not in [r["slug"] for r in queue["items"]]


async def test_an_operator_checks_a_centre_and_its_organisation_is_told(client, db, place):
    from api.modules.notifications.models import Notification

    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Visited", place))
    ).json()["slug"]
    operator = await _staff(client, db)

    granted = await client.post(
        f"/ops/organisations/{slug}/verification",
        headers=operator,
        json={"decision": "granted", "note": "Signboard seen on site"},
    )
    assert granted.status_code == 200 and granted.json()["is_verified"] is True
    centre = (await client.get(f"/org/{org}/centres/{slug}", headers=headers)).json()
    assert centre["is_verified"] is True
    parent = await _tenant(db, org)
    # The organisation's own mark is untouched by checking a centre.
    assert parent.verified_at is None
    queued = (
        await db.scalars(
            select(Notification).where(
                Notification.recipient_kind == "tenant",
                Notification.recipient_id == parent.id,
                Notification.template == "centre_verified",
            )
        )
    ).all()
    assert len(queued) == 1
    assert "Signboard" not in str(queued[0].payload), "the operator's note is evidence, not mail"

    again = await client.post(
        f"/ops/organisations/{slug}/verification",
        headers=operator,
        json={"decision": "granted", "note": "Checked again on a later visit"},
    )
    assert again.status_code == 200
    count = len(
        (
            await db.scalars(
                select(Notification).where(
                    Notification.recipient_id == parent.id,
                    Notification.template == "centre_verified",
                )
            )
        ).all()
    )
    assert count == 1, "a re-grant changes nothing the organisation can see"


async def test_verifying_the_organisation_does_not_mark_its_centres(client, db, place):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Separate", place))
    ).json()["slug"]
    operator = await _staff(client, db)
    done = await client.post(
        f"/ops/organisations/{org}/verification",
        headers=operator,
        json={"decision": "granted", "note": "Registered office checked in person"},
    )
    assert done.status_code == 200
    centre = (await client.get(f"/org/{org}/centres/{slug}", headers=headers)).json()
    assert centre["is_verified"] is False


async def test_the_review_page_says_whose_centre_it_is_and_what_address_is_checked(
    client, db, place
):
    headers, org = await _deliverer(client)
    slug = (
        await client.post(f"/org/{org}/centres", headers=headers, json=_body("Detail", place))
    ).json()["slug"]
    operator = await _staff(client, db)
    centre = (await client.get(f"/ops/organisations/{slug}/verification", headers=operator)).json()
    assert centre["tenant_type"] == "training_centre"
    assert centre["parent_slug"] == org and centre["parent_name"]
    assert centre["address"] == "12 Main Road" and centre["district"] == place[1]
    parent = (await client.get(f"/ops/organisations/{org}/verification", headers=operator)).json()
    assert parent["tenant_type"] == "course_provider"
    assert parent["parent_slug"] is None and parent["address"] is None
