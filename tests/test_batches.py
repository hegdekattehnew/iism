"""Sprint 98 (ADR-103, BL-18.5): a batch is one run of one course at one centre.

What matters here: a batch is only for a course the organisation may deliver (its own, or one it
holds an approval for), asked again at publication; what a batch *is* now (open, full, running,
finished) is derived and the SQL filter agrees with the pure function; a running class is never
stopped by anything; revoking an arrangement cancels what has not started and tells the learners
who had registered, once, in fixed words; a centre cannot close, and a course cannot be deleted,
from under a live batch; and a stranger, a seller and a centre's manager each reach exactly what
they should.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import today_ist
from api.modules import batches
from api.modules.analytics.models import AnalyticsEvent
from api.modules.batches import phases, service
from api.modules.batches.models import Batch, BatchInterest
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateProfile, Course
from api.modules.notifications.models import Notification
from api.modules.skills.hierarchy import Sector
from api.modules.skills.models import Skill
from tests.test_centre_staff import _manager
from tests.test_centres import _body as _centre_body
from tests.test_centres import _deliverer
from tests.test_training_organisations import _register, _tenant

H = dict[str, str]


@pytest.fixture
async def a_skill(db: AsyncSession) -> str:
    sector = Sector(
        sector_ref=f"b-{uuid.uuid4().hex[:6]}",
        name="Batch Fixtures",
        slug=f"bf-{uuid.uuid4().hex[:6]}",
    )
    db.add(sector)
    await db.flush()
    skill = Skill(
        slug=f"batch-skill-{uuid.uuid4().hex[:8]}",
        name="A standard to teach",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code=f"BAT/N{uuid.uuid4().int % 9000 + 1000}",
        source="nsqf",
        sector_id=sector.id,
    )
    db.add(skill)
    await db.commit()
    return skill.slug


async def _course(client, headers, org, skill, title="Welding basics", **over) -> str:
    made = await client.post(
        f"/org/{org}/courses",
        headers=headers,
        json={
            "title": title,
            "skills": [{"skill_slug": skill, "level_taught": 4}],
            **over,
        },
    )
    assert made.status_code == 201, made.text
    slug = made.json()["slug"]
    published = await client.post(f"/org/{org}/courses/{slug}/publish", headers=headers)
    assert published.status_code == 200, published.text
    return slug


async def _centre(client, headers, org, place, name="Hadapsar") -> str:
    made = await client.post(f"/org/{org}/centres", headers=headers, json=_centre_body(name, place))
    assert made.status_code == 201, made.text
    return made.json()["slug"]


def _dates(start_in: int = 14, length: int = 30) -> dict[str, str]:
    start = today_ist() + timedelta(days=start_in)
    return {
        "starts_on": start.isoformat(),
        "ends_on": (start + timedelta(days=length)).isoformat(),
    }


def _plan(course: str, centre: str | None = None, **over: object) -> dict[str, object]:
    return {"course_slug": course, "centre_slug": centre, "seats": 20, **_dates(), **over}


async def _make(client, headers, org, course, centre=None, **over):
    return await client.post(
        f"/org/{org}/batches", headers=headers, json=_plan(course, centre, **over)
    )


async def _live(client, headers, org, course, centre, **over) -> str:
    made = await _make(client, headers, org, course, centre, **over)
    assert made.status_code == 201, made.text
    batch = made.json()["id"]
    published = await client.post(f"/org/{org}/batches/{batch}/publish", headers=headers)
    assert published.status_code == 200, published.text
    return batch


async def _interest(db: AsyncSession, batch_id: str, status: str = "registered") -> uuid.UUID:
    user = User(phone=f"+91{9000000000 + uuid.uuid4().int % 999_999_999}")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(user_id=user.id)
    db.add(profile)
    await db.flush()
    db.add(BatchInterest(batch_id=uuid.UUID(batch_id), profile_id=profile.id, status=status))
    await db.commit()
    return user.id


async def _set(db: AsyncSession, batch_id: str, **values: object) -> None:
    await db.execute(update(Batch).where(Batch.id == uuid.UUID(batch_id)).values(**values))
    await db.commit()


async def _row(db: AsyncSession, batch_id: str) -> Batch:
    row = await db.scalar(
        select(Batch)
        .where(Batch.id == uuid.UUID(batch_id))
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def _approve_all(client, seller_h, seller, partner) -> str:
    made = await client.post(
        f"/org/{seller}/delivery/invitations",
        headers=seller_h,
        json={"organisation_slug": partner, "course_slug": None},
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


@pytest.fixture
async def world(client: AsyncClient, db: AsyncSession, place, a_skill):
    """A seller with a course; a delivering partner with a centre; no arrangement between them."""
    seller_h, seller = await _register(client, f"Seller {uuid.uuid4().hex[:6]}", sells=True)
    partner_h, partner = await _deliverer(client)
    welding = await _course(client, seller_h, seller, a_skill)
    centre = await _centre(client, partner_h, partner, place)
    return {
        "seller_h": seller_h,
        "seller": seller,
        "partner_h": partner_h,
        "partner": partner,
        "course": welding,
        "centre": centre,
        "skill": a_skill,
        "place": place,
    }


# ---------------------------------------------------------------- the pure rules


@pytest.mark.parametrize(
    ("status", "start", "end", "seats", "enrolled", "expected"),
    [
        ("draft", 5, 9, 10, 0, "draft"),
        ("cancelled", 5, 9, 10, 0, "cancelled"),
        ("published", 5, 9, 10, 9, "open"),
        ("published", 5, 9, 10, 10, "full"),
        ("published", 5, 9, 10, 11, "full"),
        ("published", 0, 9, 10, 0, "running"),
        ("published", -3, 0, 10, 10, "running"),
        ("published", -9, -1, 10, 0, "finished"),
        ("cancelled", -9, -1, 10, 0, "cancelled"),
    ],
)
def test_what_a_batch_is_today(status, start, end, seats, enrolled, expected) -> None:
    today = today_ist()
    assert (
        phases.phase(
            status=status,
            starts_on=today + timedelta(days=start),
            ends_on=today + timedelta(days=end),
            seats=seats,
            enrolled=enrolled,
            today=today,
        )
        == expected
    )


def test_seats_left_is_never_negative() -> None:
    assert phases.seats_left(seats=10, enrolled=4) == 6
    assert phases.seats_left(seats=10, enrolled=10) == 0
    assert phases.seats_left(seats=10, enrolled=12) == 0


def test_only_a_batch_not_yet_started_can_be_changed() -> None:
    assert {"draft", "open", "full"} == phases.CANCELLABLE


# ---------------------------------------------------------------- making and publishing


async def test_an_organisation_plans_a_batch_of_its_own_course(client, db, place, a_skill):
    headers, org = await _register(
        client, f"Both {uuid.uuid4().hex[:6]}", sells=True, delivers=True
    )
    course = await _course(client, headers, org, a_skill, fee_inr=4000)
    centre = await _centre(client, headers, org, place)

    made = await _make(client, headers, org, course, centre, label="Morning", fee_inr=3500)
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["status"] == "draft" and body["phase"] == "draft"
    assert body["course"]["own"] is True and body["course"]["provider"]["slug"] == org
    assert body["organisation"]["slug"] == org and body["centre"]["slug"] == centre
    assert (body["seats"], body["enrolled"], body["seats_left"]) == (20, 0, 20)
    assert (body["fee_inr"], body["fee_effective"], body["fee_is_override"]) == (3500, 3500, True)

    published = await client.post(f"/org/{org}/batches/{body['id']}/publish", headers=headers)
    assert published.status_code == 200 and published.json()["phase"] == "open"
    assert published.json()["published_at"] is not None

    names = set(
        (
            await db.scalars(
                select(AnalyticsEvent.name).where(
                    AnalyticsEvent.name.in_(("batch_created", "batch_published"))
                )
            )
        ).all()
    )
    assert names == {"batch_created", "batch_published"}


async def test_without_a_fee_the_courses_fee_is_the_effective_one(client, place, a_skill):
    headers, org = await _register(
        client, f"Both {uuid.uuid4().hex[:6]}", sells=True, delivers=True
    )
    course = await _course(client, headers, org, a_skill, fee_inr=4000)
    centre = await _centre(client, headers, org, place)
    body = (await _make(client, headers, org, course, centre)).json()
    assert (body["fee_inr"], body["fee_effective"], body["fee_is_override"]) == (None, 4000, False)


async def test_a_partner_needs_the_sellers_approval_to_deliver_its_course(client, db, world):
    w = world
    refused = await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    assert refused.status_code == 403
    assert "not authorised" in refused.json()["detail"]
    assert (await db.scalar(select(Batch.id))) is None

    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    made = await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    assert made.status_code == 201, made.text
    assert made.json()["course"]["own"] is False
    assert made.json()["course"]["provider"]["slug"] == w["seller"]


async def test_publishing_asks_again_and_a_revoked_draft_cannot_go_live(client, db, world):
    w = world
    row = await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    draft = (await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])).json()
    # The arrangement ends; the sweep cancels the draft, so it cannot be published.
    ended = await client.post(f"/org/{w['seller']}/delivery/{row}/revoke", headers=w["seller_h"])
    assert ended.status_code == 200
    again = await client.post(
        f"/org/{w['partner']}/batches/{draft['id']}/publish", headers=w["partner_h"]
    )
    assert again.status_code == 409
    assert (await _row(db, draft["id"])).status == "cancelled"


async def test_a_batch_needs_a_published_course(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    draft = (await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])).json()
    course = await db.scalar(select(Course).where(Course.slug == w["course"]))
    assert course is not None
    await db.execute(update(Course).where(Course.id == course.id).values(status="draft"))
    await db.commit()
    blocked = await client.post(
        f"/org/{w['partner']}/batches/{draft['id']}/publish", headers=w["partner_h"]
    )
    assert blocked.status_code == 409 and "not published" in blocked.json()["detail"]
    fresh = await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    assert fresh.status_code == 409

    await db.execute(update(Course).where(Course.id == course.id).values(status="published"))
    await db.commit()
    assert (
        await client.post(
            f"/org/{w['partner']}/batches/{draft['id']}/publish", headers=w["partner_h"]
        )
    ).status_code == 200


async def test_dates_seats_and_a_centre_are_checked(client, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])

    def post(**over):
        return _make(client, w["partner_h"], w["partner"], w["course"], w["centre"], **over)

    past = (today_ist() - timedelta(days=1)).isoformat()
    assert (await post(starts_on=past, ends_on=past)).status_code == 422
    backwards = _dates()
    assert (
        await post(ends_on=backwards["starts_on"], starts_on=_dates(20)["starts_on"])
    ).status_code == 422
    assert (await post(seats=0)).status_code == 422
    assert (await post(seats=5001)).status_code == 422
    assert (await post(fee_inr=-1)).status_code == 422
    assert (await post(mode="teleport")).status_code == 422
    no_centre = await _make(client, w["partner_h"], w["partner"], w["course"], None)
    assert no_centre.status_code == 422
    elsewhere = await _make(client, w["partner_h"], w["partner"], w["course"], "no-such-centre")
    assert elsewhere.status_code == 404


async def test_publishing_twice_is_a_conflict_and_a_started_draft_cannot_publish(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    again = await client.post(
        f"/org/{w['partner']}/batches/{batch}/publish", headers=w["partner_h"]
    )
    assert again.status_code == 409

    draft = (await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])).json()
    await _set(db, draft["id"], starts_on=today_ist() - timedelta(days=2))
    late = await client.post(
        f"/org/{w['partner']}/batches/{draft['id']}/publish", headers=w["partner_h"]
    )
    assert late.status_code == 409 and "already passed" in late.json()["detail"]


# ---------------------------------------------------------------- who reaches what


async def test_only_an_organisation_that_delivers_has_batches(client, world):
    w = world
    for path in ("", "/courses"):
        got = await client.get(f"/org/{w['seller']}/batches{path}", headers=w["seller_h"])
        assert got.status_code == 403, "a seller that does not deliver has no batches"
    made = await _make(client, w["seller_h"], w["seller"], w["course"], "x")
    assert made.status_code == 403


async def test_a_stranger_and_another_organisation_get_the_same_404(client, world, place, a_skill):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    other_h, other = await _deliverer(client)
    stranger = await client.get(f"/org/{w['partner']}/batches", headers=other_h)
    assert stranger.status_code == 404
    mine = await client.get(f"/org/{other}/batches/{batch}", headers=other_h)
    nothing = await client.get(f"/org/{other}/batches/{uuid.uuid4()}", headers=other_h)
    assert mine.status_code == nothing.status_code == 404
    assert mine.json() == nothing.json(), "another organisation's batch is indistinguishable"
    for verb in ("publish", "cancel"):
        refused = await client.post(f"/org/{other}/batches/{batch}/{verb}", headers=other_h)
        assert refused.status_code == 404
    put = await client.put(
        f"/org/{other}/batches/{batch}", headers=other_h, json={"seats": 3, **_dates()}
    )
    assert put.status_code == 404


async def test_a_member_may_read_but_not_change(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    from api.modules.identity.models import Membership

    tenant = await _tenant(db, w["partner"])
    owner = await db.scalar(select(Membership).where(Membership.tenant_id == tenant.id))
    assert owner is not None
    owner.role = "member"
    await db.commit()
    read = await client.get(f"/org/{w['partner']}/batches", headers=w["partner_h"])
    assert read.status_code == 200 and read.json()["total"] == 1
    for verb in ("publish", "cancel"):
        refused = await client.post(
            f"/org/{w['partner']}/batches/{batch}/{verb}", headers=w["partner_h"]
        )
        assert refused.status_code == 403
    assert (
        await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    ).status_code == 403


async def test_a_centres_manager_reads_only_their_own_centre(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    second = await _centre(client, w["partner_h"], w["partner"], w["place"], "Kothrud")
    here = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    there = await _live(client, w["partner_h"], w["partner"], w["course"], second)
    manager = await _manager(client, db, w["partner_h"], w["partner"], w["centre"])

    listed = await client.get(f"/org/{w['centre']}/batches", headers=manager)
    assert listed.status_code == 200
    assert [b["id"] for b in listed.json()["items"]] == [here]
    assert (
        await client.get(f"/org/{w['centre']}/batches/{here}", headers=manager)
    ).status_code == 200
    sibling = await client.get(f"/org/{w['centre']}/batches/{there}", headers=manager)
    assert sibling.status_code == 404, "a manager cannot reach a sibling centre's batch"
    # Reading is theirs; planning a run commits the organisation, and is not yet. Nor is the list of
    # courses to plan from: it names the organisation's arrangements with other organisations.
    assert (
        await client.get(f"/org/{w['centre']}/batches/courses", headers=manager)
    ).status_code == 403
    planned = await _make(client, manager, w["centre"], w["course"], None)
    assert planned.status_code == 403
    cancelled = await client.post(f"/org/{w['centre']}/batches/{here}/cancel", headers=manager)
    assert cancelled.status_code == 403
    # ...and the organisation's own route is closed to them.
    assert (await client.get(f"/org/{w['partner']}/batches", headers=manager)).status_code == 404


async def test_the_courses_a_batch_can_be_made_of(client, world, a_skill):
    w = world
    own_h, own = await _register(client, f"Own {uuid.uuid4().hex[:6]}", sells=True, delivers=True)
    mine = await _course(client, own_h, own, a_skill, "My own course")
    listed = (await client.get(f"/org/{own}/batches/courses", headers=own_h)).json()
    assert [c["slug"] for c in listed["items"]] == [mine] and listed["items"][0]["own"] is True

    empty = (
        await client.get(f"/org/{w['partner']}/batches/courses", headers=w["partner_h"])
    ).json()
    assert empty["items"] == []
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    got = (await client.get(f"/org/{w['partner']}/batches/courses", headers=w["partner_h"])).json()
    assert [c["slug"] for c in got["items"]] == [w["course"]]
    assert got["items"][0]["own"] is False and got["items"][0]["provider"]["slug"] == w["seller"]


# ---------------------------------------------------------------- changing a batch


async def test_seats_cannot_drop_below_the_learners_enrolled(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"], seats=10)
    for _ in range(3):
        await _interest(db, batch, "enrolled")
    await _interest(db, batch, "registered")
    body = (await client.get(f"/org/{w['partner']}/batches/{batch}", headers=w["partner_h"])).json()
    assert (body["enrolled"], body["interested"], body["seats_left"]) == (3, 4, 7)

    def put(**over):
        return client.put(
            f"/org/{w['partner']}/batches/{batch}",
            headers=w["partner_h"],
            json={**_dates(), "seats": 10, **over},
        )

    refused = await put(seats=2)
    assert refused.status_code == 409 and "3 learners" in refused.json()["detail"]
    assert (await put(seats=3)).json()["phase"] == "full"
    assert (await put(seats=8, label="Evening")).json()["seats_left"] == 5
    # Learners registered for these dates: moving them is cancelling and making a new batch.
    moved = await put(**_dates(40))
    assert moved.status_code == 409 and "Cancel this batch" in moved.json()["detail"]


async def test_a_draft_can_move_dates_freely(client, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    draft = (await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])).json()
    moved = await client.put(
        f"/org/{w['partner']}/batches/{draft['id']}",
        headers=w["partner_h"],
        json={**_dates(60), "seats": 12},
    )
    assert moved.status_code == 200 and moved.json()["seats"] == 12


async def test_a_class_in_progress_is_never_changed_or_cancelled(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    await _set(db, batch, starts_on=today_ist())
    now = (await client.get(f"/org/{w['partner']}/batches/{batch}", headers=w["partner_h"])).json()
    assert now["phase"] == "running"
    cancel = await client.post(
        f"/org/{w['partner']}/batches/{batch}/cancel", headers=w["partner_h"]
    )
    assert cancel.status_code == 409 and "in progress" in cancel.json()["detail"]
    put = await client.put(
        f"/org/{w['partner']}/batches/{batch}",
        headers=w["partner_h"],
        json={"seats": 5, **_dates(1)},
    )
    assert put.status_code == 409
    assert (await _row(db, batch)).status == "published"


# ---------------------------------------------------------------- cancelling


async def _notices_to(db: AsyncSession, user_id: uuid.UUID) -> list[Notification]:
    return list(
        (
            await db.scalars(
                select(Notification).where(
                    Notification.recipient_kind == "user",
                    Notification.recipient_id == user_id,
                    Notification.template == "batch_cancelled",
                )
            )
        ).all()
    )


async def test_cancelling_tells_each_registered_learner_once_in_fixed_words(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    registered = await _interest(db, batch, "registered")
    enrolled = await _interest(db, batch, "enrolled")
    withdrawn = await _interest(db, batch, "withdrawn")

    done = await client.post(f"/org/{w['partner']}/batches/{batch}/cancel", headers=w["partner_h"])
    assert done.status_code == 200, done.text
    assert done.json()["phase"] == "cancelled" and done.json()["cancel_reason"] == "by_organisation"

    for who in (registered, enrolled):
        notices = await _notices_to(db, who)
        assert len(notices) == 1 and notices[0].channel == "in_app"
        assert set(notices[0].payload) == {"course", "reason", "path"}
        assert notices[0].payload["reason"] == "by_organisation"
        assert notices[0].payload["path"] == f"/courses/{w['course']}"
    assert await _notices_to(db, withdrawn) == [], "a learner who withdrew is not told"
    again = await client.post(f"/org/{w['partner']}/batches/{batch}/cancel", headers=w["partner_h"])
    assert again.status_code == 409
    assert len(await _notices_to(db, registered)) == 1, "a second cancel tells nobody again"


# ---------------------------------------------------------------- the arrangement ends


async def test_revoking_cancels_what_has_not_started_and_lets_the_running_finish(client, db, world):
    w = world
    row = await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    future = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    draft = (await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])).json()[
        "id"
    ]
    running = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    await _set(db, running, starts_on=today_ist())
    waiting = await _interest(db, future, "registered")
    attending = await _interest(db, running, "enrolled")

    ended = await client.post(f"/org/{w['seller']}/delivery/{row}/revoke", headers=w["seller_h"])
    assert ended.status_code == 200, ended.text

    for gone in (future, draft):
        cancelled = await _row(db, gone)
        assert (cancelled.status, cancelled.cancel_reason) == ("cancelled", "arrangement_ended")
    assert (await _row(db, running)).status == "published", "a class in progress finishes"
    assert len(await _notices_to(db, waiting)) == 1
    assert await _notices_to(db, attending) == []
    notice = (await _notices_to(db, waiting))[0]
    assert notice.payload["reason"] == "arrangement_ended"


async def test_another_arrangement_that_still_covers_the_course_keeps_the_batch(client, db, world):
    w = world
    one = await client.post(
        f"/org/{w['seller']}/delivery/invitations",
        headers=w["seller_h"],
        json={"organisation_slug": w["partner"], "course_slug": w["course"]},
    )
    everything = await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    await client.post(
        f"/org/{w['seller']}/delivery/{one.json()['id']}/revoke", headers=w["seller_h"]
    )
    assert (await _row(db, batch)).status == "published", "the all-courses approval still covers it"
    await client.post(f"/org/{w['seller']}/delivery/{everything}/revoke", headers=w["seller_h"])
    assert (await _row(db, batch)).status == "cancelled"


async def test_the_partner_ending_it_cancels_the_same_way(client, db, world):
    w = world
    row = await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    await client.post(f"/org/{w['partner']}/delivery/{row}/revoke", headers=w["partner_h"])
    assert (await _row(db, batch)).cancel_reason == "arrangement_ended"


async def test_a_declined_request_has_no_batches_to_cancel(client, db, world):
    w = world
    made = await client.post(
        f"/org/{w['partner']}/delivery/requests",
        headers=w["partner_h"],
        json={"organisation_slug": w["seller"], "course_slug": w["course"]},
    )
    await client.post(
        f"/org/{w['seller']}/delivery/{made.json()['id']}/decline", headers=w["seller_h"]
    )
    assert (await db.scalar(select(Batch.id))) is None


async def test_ones_own_course_is_untouched_by_an_arrangement_ending(
    client, db, place, a_skill, world
):
    w = world
    both_h, both = await _register(
        client, f"Both {uuid.uuid4().hex[:6]}", sells=True, delivers=True
    )
    mine = await _course(client, both_h, both, a_skill, "Mine")
    centre = await _centre(client, both_h, both, place)
    row = (
        await client.post(
            f"/org/{w['seller']}/delivery/invitations",
            headers=w["seller_h"],
            json={"organisation_slug": both, "course_slug": None},
        )
    ).json()["id"]
    own_batch = await _live(client, both_h, both, mine, centre)
    theirs = await _live(client, both_h, both, w["course"], centre)
    await client.post(f"/org/{w['seller']}/delivery/{row}/revoke", headers=w["seller_h"])
    assert (await _row(db, own_batch)).status == "published"
    assert (await _row(db, theirs)).status == "cancelled"


# ---------------------------------------------------------------- what a live batch keeps alive


async def test_a_centre_cannot_close_from_under_a_batch_and_can_once_it_is_over(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    path = f"/org/{w['partner']}/centres/{w['centre']}/close"
    refused = await client.post(path, headers=w["partner_h"])
    assert refused.status_code == 409 and "1 batch" in refused.json()["detail"]

    await _set(
        db,
        batch,
        starts_on=today_ist() - timedelta(days=10),
        ends_on=today_ist() - timedelta(days=1),
    )
    assert (await client.post(path, headers=w["partner_h"])).status_code == 200

    blocked = await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    assert blocked.status_code == 409 and "closed" in blocked.json()["detail"]


async def test_a_draft_also_keeps_the_centre_open(client, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    draft = (await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])).json()
    path = f"/org/{w['partner']}/centres/{w['centre']}/close"
    assert (await client.post(path, headers=w["partner_h"])).status_code == 409
    await client.post(f"/org/{w['partner']}/batches/{draft['id']}/cancel", headers=w["partner_h"])
    assert (await client.post(path, headers=w["partner_h"])).status_code == 200


async def test_a_course_with_a_live_batch_cannot_be_deleted(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    path = f"/org/{w['seller']}/courses/{w['course']}"
    refused = await client.delete(path, headers=w["seller_h"])
    assert refused.status_code == 409 and "batch" in refused.json()["detail"]
    await client.post(f"/org/{w['partner']}/batches/{batch}/cancel", headers=w["partner_h"])
    assert (await client.delete(path, headers=w["seller_h"])).status_code in (200, 204)


# ---------------------------------------------------------------- the list


async def test_the_sql_filter_agrees_with_the_pure_function_for_every_phase(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    today = today_ist()
    made: dict[str, str] = {}
    made["draft"] = (
        await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    ).json()["id"]
    made["open"] = await _live(
        client, w["partner_h"], w["partner"], w["course"], w["centre"], seats=5
    )
    made["full"] = await _live(
        client, w["partner_h"], w["partner"], w["course"], w["centre"], seats=1
    )
    await _interest(db, made["full"], "enrolled")
    made["running"] = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    await _set(db, made["running"], starts_on=today)
    made["finished"] = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    await _set(
        db, made["finished"], starts_on=today - timedelta(days=9), ends_on=today - timedelta(days=1)
    )
    made["cancelled"] = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    await client.post(
        f"/org/{w['partner']}/batches/{made['cancelled']}/cancel", headers=w["partner_h"]
    )

    for name, batch_id in made.items():
        listed = (
            await client.get(
                f"/org/{w['partner']}/batches", headers=w["partner_h"], params={"phase": name}
            )
        ).json()
        assert [b["id"] for b in listed["items"]] == [batch_id], name
        assert listed["total"] == 1 and listed["items"][0]["phase"] == name

    everything = (await client.get(f"/org/{w['partner']}/batches", headers=w["partner_h"])).json()
    assert everything["total"] == 6 and {b["phase"] for b in everything["items"]} == set(made)


async def test_the_total_is_the_count_not_the_page_and_paging_does_not_swap_rows(client, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    for _ in range(5):
        await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    first = (
        await client.get(
            f"/org/{w['partner']}/batches", headers=w["partner_h"], params={"limit": 2}
        )
    ).json()
    second = (
        await client.get(
            f"/org/{w['partner']}/batches", headers=w["partner_h"], params={"limit": 2, "offset": 2}
        )
    ).json()
    third = (
        await client.get(
            f"/org/{w['partner']}/batches", headers=w["partner_h"], params={"limit": 2, "offset": 4}
        )
    ).json()
    assert first["total"] == second["total"] == third["total"] == 5
    seen = [b["id"] for page in (first, second, third) for b in page["items"]]
    assert len(seen) == 5 and len(set(seen)) == 5


async def test_filtering_by_centre_and_by_course(client, world, a_skill):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    other_course = await _course(client, w["seller_h"], w["seller"], a_skill, "Plumbing basics")
    second = await _centre(client, w["partner_h"], w["partner"], w["place"], "Kothrud")
    a = (await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])).json()["id"]
    b = (await _make(client, w["partner_h"], w["partner"], other_course, second)).json()["id"]

    def listed(**params):
        return client.get(f"/org/{w['partner']}/batches", headers=w["partner_h"], params=params)

    assert [x["id"] for x in (await listed(centre=second)).json()["items"]] == [b]
    assert [x["id"] for x in (await listed(course=w["course"])).json()["items"]] == [a]
    assert (await listed(phase="bogus")).status_code == 422


# ---------------------------------------------------------------- erasure


async def test_deleting_an_organisation_tells_the_learners_of_its_batches(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    learner = await _interest(db, batch, "registered")

    # Deleting the *organisation that runs it* tells them the centre is gone; deleting the *seller*
    # (whose course goes with it) tells them the course is. Each once, nothing else.
    sent = await batches.tell_before_deleting(db, (await _tenant(db, w["partner"])).id)
    assert sent == 1
    sent += await batches.tell_before_deleting(db, (await _tenant(db, w["seller"])).id)
    assert sent == 2
    reasons = sorted(n.payload["reason"] for n in await _notices_to(db, learner))
    assert reasons == ["centre_closed", "course_unavailable"]


async def test_deleting_the_organisation_through_the_route_tells_and_removes(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    learner = await _interest(db, batch, "registered")

    gone = await client.delete(f"/org/{w['partner']}", headers=w["partner_h"])
    assert gone.status_code == 204, gone.text
    assert (await db.scalar(select(Batch.id).where(Batch.id == uuid.UUID(batch)))) is None
    assert (
        await db.scalar(select(BatchInterest.id).where(BatchInterest.batch_id == uuid.UUID(batch)))
    ) is None
    notices = await _notices_to(db, learner)
    assert [n.payload["reason"] for n in notices] == ["centre_closed"]


async def test_deleting_the_seller_through_the_route_tells_the_partners_learners(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    batch = await _live(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    learner = await _interest(db, batch, "registered")
    assert (await client.delete(f"/org/{w['seller']}", headers=w["seller_h"])).status_code == 204
    assert [n.payload["reason"] for n in await _notices_to(db, learner)] == ["course_unavailable"]
    assert (await db.scalar(select(Batch.id).where(Batch.id == uuid.UUID(batch)))) is None


async def test_publishing_asks_the_arrangement_itself_not_only_the_sweep(client, db, world):
    """A draft left behind an ended arrangement (the sweep missed it, or the row was changed by
    hand) still cannot be published: the writer asks again, under lock."""
    from api.modules.delivery import CourseDeliveryAuthorisation as Arrangement

    w = world
    row = await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    draft = (await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])).json()
    await db.execute(
        update(Arrangement)
        .where(Arrangement.id == uuid.UUID(row))
        .values(ended_at=datetime.now(UTC), ended_by_side="provider")
    )
    await db.commit()
    refused = await client.post(
        f"/org/{w['partner']}/batches/{draft['id']}/publish", headers=w["partner_h"]
    )
    assert refused.status_code == 403 and "not authorised" in refused.json()["detail"]
    assert (await _row(db, draft["id"])).status == "draft"


async def test_a_centre_of_another_organisation_is_not_found_by_name(client, world, place):
    w = world
    other_h, other = await _deliverer(client)
    await _centre(client, other_h, other, place, "Elsewhere")
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    # The other organisation also needs to be allowed the course, so the 404 is the centre's.
    await _approve_all(client, w["seller_h"], w["seller"], other)
    mine = await _make(client, other_h, other, w["course"], w["centre"])
    assert mine.status_code == 404, "another organisation's centre is not found, not forbidden"
    assert mine.json()["detail"] == "Centre not found"


async def test_a_centre_names_only_itself(db, world):
    from fastapi import HTTPException

    w = world
    tenant = await _tenant(db, w["centre"])
    assert (await service._resolve_centre(db, tenant, None)).id == tenant.id
    assert (await service._resolve_centre(db, tenant, w["centre"])).id == tenant.id
    with pytest.raises(HTTPException) as refusal:
        await service._resolve_centre(db, tenant, "some-other-centre")
    assert refusal.value.status_code == 404


async def test_only_published_courses_are_offered(client, a_skill):
    own_h, own = await _register(client, f"Own {uuid.uuid4().hex[:6]}", sells=True, delivers=True)
    live = await _course(client, own_h, own, a_skill, "Live course")
    draft = await client.post(
        f"/org/{own}/courses",
        headers=own_h,
        json={"title": "Still a draft", "skills": [{"skill_slug": a_skill, "level_taught": 4}]},
    )
    assert draft.status_code == 201
    listed = (await client.get(f"/org/{own}/batches/courses", headers=own_h)).json()
    assert [c["slug"] for c in listed["items"]] == [live]


async def test_a_centre_has_a_cap_on_batches_that_are_not_over(client, world, monkeypatch):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    monkeypatch.setattr(service, "MAX_LIVE_PER_CENTRE", 2)
    for _ in range(2):
        assert (
            await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
        ).status_code == 201
    capped = await _make(client, w["partner_h"], w["partner"], w["course"], w["centre"])
    assert capped.status_code == 409 and "up to 2 batches" in capped.json()["detail"]


def test_the_module_registers_itself_with_delivery() -> None:
    from api.modules.delivery import service as delivery_service

    assert service.cancel_on_arrangement_ended in delivery_service._on_ended
