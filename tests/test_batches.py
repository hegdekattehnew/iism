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
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import today_ist
from api.modules import batches
from api.modules.analytics.models import AnalyticsEvent
from api.modules.batches import bulk as bulk_module
from api.modules.batches import phases, service
from api.modules.batches.models import Batch, BatchInterest
from api.modules.identity.models import Tenant, User
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


async def test_a_centres_manager_works_in_their_own_centre_only(client, db, world):
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
    # Planning is theirs too (Sprint 99), in their own centre and nowhere else.
    mine = await _make(client, manager, w["centre"], w["course"], None)
    assert mine.status_code == 201, mine.text
    assert mine.json()["centre"]["slug"] == w["centre"]
    elsewhere = await _make(client, manager, w["centre"], w["course"], second)
    assert elsewhere.status_code == 404, "a manager cannot plan into a sibling centre"
    published = await client.post(
        f"/org/{w['centre']}/batches/{mine.json()['id']}/publish", headers=manager
    )
    assert published.status_code == 200
    cancelled = await client.post(f"/org/{w['centre']}/batches/{here}/cancel", headers=manager)
    assert cancelled.status_code == 200
    sibling_cancel = await client.post(
        f"/org/{w['centre']}/batches/{there}/cancel", headers=manager
    )
    assert sibling_cancel.status_code == 404
    # A file of batches names a centre on every row: the organisation's, never a manager's.
    template = await client.get(f"/org/{w['centre']}/batches/bulk/template", headers=manager)
    assert template.status_code in (403, 404)
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


# ---------------------------------------------------------------- Sprint 99: the home's figures


def _day(n: int) -> str:
    return (today_ist() + timedelta(days=n)).isoformat()


async def _plan_at(client, w, *, start, length=20, seats=10, course=None, centre=None, **over):
    made = await client.post(
        f"/org/{w['partner']}/batches",
        headers=w["partner_h"],
        json={
            "course_slug": course or w["course"],
            "centre_slug": centre or w["centre"],
            "starts_on": _day(start),
            "ends_on": _day(start + length),
            "seats": seats,
            **over,
        },
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


async def _publish(client, w, batch_id):
    done = await client.post(
        f"/org/{w['partner']}/batches/{batch_id}/publish", headers=w["partner_h"]
    )
    assert done.status_code == 200, done.text


async def test_the_overview_counts_what_needs_a_look(client, db, world, a_skill):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    await _plan_at(client, w, start=40)  # a draft
    soon = await _plan_at(client, w, start=3, seats=10)
    await _publish(client, w, soon)
    await _interest(db, soon, "enrolled")
    await _interest(db, soon, "enrolled")
    fortnight = await _plan_at(client, w, start=10, seats=5)
    await _publish(client, w, fortnight)
    far = await _plan_at(client, w, start=60, seats=7)
    await _publish(client, w, far)
    running = await _plan_at(client, w, start=1)
    await _publish(client, w, running)
    await _set(db, running, starts_on=today_ist())
    # Full and about to begin: no seat to fill, so it is in neither figure.
    full = await _plan_at(client, w, start=8, seats=1)
    await _publish(client, w, full)
    await _interest(db, full, "enrolled")
    cancelled = await _plan_at(client, w, start=5)
    await _publish(client, w, cancelled)
    await client.post(f"/org/{w['partner']}/batches/{cancelled}/cancel", headers=w["partner_h"])

    got = (await client.get(f"/org/{w['partner']}/batches/overview", headers=w["partner_h"])).json()
    assert got["drafts"] == 1
    assert got["starting_soon"] == 1, "only the one beginning within the week"
    assert got["running"] == 1
    # 8 free in the first, 5 in the second; the batch 60 days away is not about to begin.
    assert (got["unfilled_seats"], got["unfilled_batches"]) == (13, 2)
    assert got["unavailable"] == 0
    assert [b["id"] for b in got["upcoming"]] == [soon, full, fortnight, far], (
        "soonest first, published only"
    )

    # A course that stops being live puts its batches in front of the organisation.
    await db.execute(update(Course).where(Course.slug == w["course"]).values(status="draft"))
    await db.commit()
    again = (
        await client.get(f"/org/{w['partner']}/batches/overview", headers=w["partner_h"])
    ).json()
    assert again["unavailable"] == 6, "every batch not yet over, drafts included, of that course"


async def test_the_overview_is_each_organisations_and_each_centres_own(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    second = await _centre(client, w["partner_h"], w["partner"], w["place"], "Kothrud")
    here = await _plan_at(client, w, start=2)
    await _publish(client, w, here)
    there = await _plan_at(client, w, start=3, centre=second)
    await _publish(client, w, there)
    manager = await _manager(client, db, w["partner_h"], w["partner"], w["centre"])

    mine = (await client.get(f"/org/{w['centre']}/batches/overview", headers=manager)).json()
    assert mine["starting_soon"] == 1 and [b["id"] for b in mine["upcoming"]] == [here]
    whole = (
        await client.get(f"/org/{w['partner']}/batches/overview", headers=w["partner_h"])
    ).json()
    assert whole["starting_soon"] == 2

    other_h, other = await _deliverer(client)
    nobody = (await client.get(f"/org/{other}/batches/overview", headers=other_h)).json()
    assert (nobody["drafts"], nobody["starting_soon"], nobody["upcoming"]) == (0, 0, [])
    assert (
        await client.get(f"/org/{w['seller']}/batches/overview", headers=w["seller_h"])
    ).status_code == 403, "a seller that does not deliver has no figures of its own"


# ---------------------------------------------------------------- Sprint 99: the seller's counts


async def test_a_seller_sees_counts_of_how_its_courses_are_run_and_nothing_else(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    await _plan_at(client, w, start=30)  # a draft: the partner's private plan
    open_batch = await _plan_at(client, w, start=20, seats=10)
    await _publish(client, w, open_batch)
    await _interest(db, open_batch, "enrolled")
    full = await _plan_at(client, w, start=25, seats=1)
    await _publish(client, w, full)
    await _interest(db, full, "enrolled")
    running = await _plan_at(client, w, start=2)
    await _publish(client, w, running)
    await _set(db, running, starts_on=today_ist())
    finished = await _plan_at(client, w, start=2)
    await _publish(client, w, finished)
    await _set(
        db,
        finished,
        starts_on=today_ist() - timedelta(days=9),
        ends_on=today_ist() - timedelta(days=1),
    )
    cancelled = await _plan_at(client, w, start=9)
    await _publish(client, w, cancelled)
    await client.post(f"/org/{w['partner']}/batches/{cancelled}/cancel", headers=w["partner_h"])

    got = await client.get(f"/org/{w['seller']}/batches/of-my-courses", headers=w["seller_h"])
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["course"]["slug"] == w["course"] and row["organisation"]["slug"] == w["partner"]
    assert (row["batches"], row["open"], row["full"], row["running"], row["finished"]) == (
        4,
        1,
        1,
        1,
        1,
    )
    assert (row["seats"], row["enrolled"]) == (10 + 1 + 10 + 10, 2)
    # Counts and the delivering organisation: no learner, centre, contact or batch id.
    assert set(row) == {
        *("course", "organisation", "batches", "open", "full", "running", "finished"),
        *("seats", "enrolled"),
    }
    assert set(row["organisation"]) == {"slug", "name", "is_verified"}
    text = got.text
    for secret in ("contact", "phone", "email", "centre", "profile"):
        assert secret not in text


async def test_only_a_seller_reads_it_and_only_its_own_courses(client, db, world, a_skill):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    live = await _plan_at(client, w, start=20)
    await _publish(client, w, live)
    assert (
        await client.get(f"/org/{w['partner']}/batches/of-my-courses", headers=w["partner_h"])
    ).status_code == 403
    other_h, other = await _register(client, f"Other {uuid.uuid4().hex[:6]}", sells=True)
    assert (await client.get(f"/org/{other}/batches/of-my-courses", headers=other_h)).json() == {
        "items": [],
        "total": 0,
    }
    stranger = await client.get(f"/org/{w['seller']}/batches/of-my-courses", headers=other_h)
    assert stranger.status_code == 404


async def test_an_organisation_that_sells_and_delivers_sees_its_own_courses_run_too(
    client, a_skill, place
):
    both_h, both = await _register(
        client, f"Both {uuid.uuid4().hex[:6]}", sells=True, delivers=True
    )
    mine = await _course(client, both_h, both, a_skill, "Mine")
    centre = await _centre(client, both_h, both, place)
    batch = await _live(client, both_h, both, mine, centre)
    got = (await client.get(f"/org/{both}/batches/of-my-courses", headers=both_h)).json()
    assert got["total"] == 1 and got["items"][0]["open"] == 1
    assert batch


# ---------------------------------------------------------------- Sprint 99: a file of batches


def _csv(*rows: str, header: str | None = None) -> bytes:
    head = header or "course,centre,starts_on,ends_on,seats,mode,label,schedule,fee_inr"
    return ("\r\n".join([head, *rows]) + "\r\n").encode()


async def _bulk(client, w, verb, body, headers=None, org=None):
    return await client.post(
        f"/org/{org or w['partner']}/batches/bulk/{verb}",
        headers={**(headers or w["partner_h"]), "content-type": "text/csv"},
        content=body,
    )


async def test_a_file_is_checked_then_made_into_drafts_and_writes_nothing_until_then(
    client, db, world
):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    body = _csv(
        f"{w['course']},{w['centre']},{_day(30)},{_day(60)},25,hybrid,Morning,Mon to Fri,3500",
        f"{w['course']},Hadapsar Skill Centre,{_day(40)},{_day(70)},15,,,,",
    )
    checked = await _bulk(client, w, "check", body)
    assert checked.status_code == 200, checked.text
    c = checked.json()
    assert (c["applied"], c["ok"] + c["warnings"], c["errors"], c["created"]) == (False, 1, 1, 0)
    assert (await db.scalar(select(Batch.id))) is None, "a check writes nothing"

    applied = (await _bulk(client, w, "apply", body)).json()
    assert applied["applied"] is True and applied["created"] == 1
    made = [r for r in applied["rows"] if r["created"]]
    row = await _row(db, made[0]["id"])
    assert (row.status, row.seats, row.mode, row.fee_inr, row.label) == (
        "draft", 25, "hybrid", 3500, "Morning",
    )  # fmt: skip
    # Draft: nobody sees it as published, and a second apply makes nothing more.
    again = (await _bulk(client, w, "apply", body)).json()
    assert again["created"] == 0 and again["skipped"] == 1
    assert [r["id"] for r in again["rows"] if r["status"] == "skip"] == [made[0]["id"]]


async def test_the_check_and_the_apply_decide_alike(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    body = _csv(
        f"{w['course']},{w['centre']},{_day(30)},{_day(60)},25",
        f"nope,{w['centre']},{_day(30)},{_day(60)},25",
        f"{w['course']},{w['centre']},{_day(30)},{_day(60)},25",
        f"{w['course']},{w['centre']},{_day(-3)},{_day(60)},25",
    )
    before = [
        (r["row"], r["status"]) for r in (await _bulk(client, w, "check", body)).json()["rows"]
    ]
    after = [
        (r["row"], r["status"]) for r in (await _bulk(client, w, "apply", body)).json()["rows"]
    ]
    assert before == after == [(2, "ok"), (3, "error"), (4, "error"), (5, "error")]


@pytest.mark.parametrize(
    ("cells", "words"),
    [
        ("nope,{c},{a},{b},25", "No course you may deliver"),
        ("{k},nowhere,{a},{b},25", "no centre called that"),
        ("{k},{c},{p},{b},25", "cannot be in the past"),
        ("{k},{c},{b},{a},25", "before the first day"),
        ("{k},{c},{a},{b},0", "seats"),
        ("{k},{c},{a},{b},lots", "seats"),
        ("{k},{c},{a},{b},25,teleport", "mode"),
        ("{k},{c},not-a-date,{b},25", "starts_on"),
        ("{k},{c},{a},{b},25,,,,-5", "fee_inr"),
    ],
)
async def test_a_bad_row_says_what_is_wrong_and_blocks_nothing(client, world, cells, words):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    bad = cells.format(k=w["course"], c=w["centre"], a=_day(30), b=_day(60), p=_day(-3))
    body = _csv(bad, f"{w['course']},{w['centre']},{_day(31)},{_day(61)},10")
    got = (await _bulk(client, w, "apply", body)).json()
    assert got["errors"] == 1 and got["created"] == 1, "the good row still lands"
    assert words in " ".join(got["rows"][0]["messages"]), got["rows"][0]
    assert got["errors_csv"] and "error" in got["errors_csv"].splitlines()[0]


async def test_a_course_is_named_by_slug_or_exact_title_and_never_guessed(client, world, a_skill):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    twin_a = await _course(client, w["seller_h"], w["seller"], a_skill, "Twin Title")
    twin_b = await _course(client, w["seller_h"], w["seller"], a_skill, "Twin Title")
    body = _csv(
        f"Welding basics,{w['centre']},{_day(30)},{_day(60)},10",
        f"welding bas,{w['centre']},{_day(31)},{_day(61)},10",
        f"Twin Title,{w['centre']},{_day(32)},{_day(62)},10",
        f"{twin_a},{w['centre']},{_day(33)},{_day(63)},10",
        f"{twin_b},{w['centre']},{_day(34)},{_day(64)},10",
    )
    rows = (await _bulk(client, w, "check", body)).json()["rows"]
    assert [r["status"] for r in rows] == ["ok", "error", "error", "ok", "ok"]
    assert "Two of your courses have that title" in rows[2]["messages"][0]


async def test_a_course_the_organisation_may_not_deliver_is_not_in_the_file(client, world):
    w = world
    body = _csv(f"{w['course']},{w['centre']},{_day(30)},{_day(60)},10")
    refused = (await _bulk(client, w, "apply", body)).json()
    assert refused["errors"] == 1 and refused["created"] == 0
    assert "authorised" in refused["rows"][0]["messages"][0]


async def test_a_closed_centre_and_a_repeated_row_are_errors_and_a_duplicate_is_skipped(
    client, world
):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    closed = await _centre(client, w["partner_h"], w["partner"], w["place"], "Closed One")
    await client.post(f"/org/{w['partner']}/centres/{closed}/close", headers=w["partner_h"])
    line = f"{w['course']},{w['centre']},{_day(30)},{_day(60)},10,,Evening"
    body = _csv(
        f"{w['course']},{closed},{_day(30)},{_day(60)},10", line, line.replace("Evening", "evening")
    )
    rows = (await _bulk(client, w, "check", body)).json()["rows"]
    assert "closed" in rows[0]["messages"][0]
    assert rows[1]["status"] == "ok"
    assert rows[2]["status"] == "error"
    assert "appears on row 3" in rows[2]["messages"][0], "the spreadsheet's own numbering"


async def test_the_per_centre_cap_holds_in_a_file_as_it_does_by_hand(client, world, monkeypatch):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    monkeypatch.setattr(service, "MAX_LIVE_PER_CENTRE", 2)
    body = _csv(
        *[f"{w['course']},{w['centre']},{_day(30 + i)},{_day(60 + i)},10" for i in range(3)]
    )
    # The preview says it before anything is made, and the apply says the same.
    previewed = (await _bulk(client, w, "check", body)).json()["rows"]
    assert [r["status"] for r in previewed] == ["ok", "ok", "error"]
    rows = (await _bulk(client, w, "apply", body)).json()["rows"]
    assert [r["status"] for r in rows] == ["ok", "ok", "error"]
    assert "up to 2 batches" in rows[2]["messages"][0]


async def test_a_cell_that_would_be_a_formula_comes_back_inert(client, world):
    w = world
    body = _csv(f"=HYPERLINK(1),{w['centre']},{_day(30)},{_day(60)},10")
    got = (await _bulk(client, w, "check", body)).json()
    assert got["errors_csv"] is not None
    assert "'=HYPERLINK" in got["errors_csv"] and ",=HYPERLINK" not in got["errors_csv"]


async def test_an_unreadable_or_oversized_file_is_refused_before_any_row(client, world):
    w = world
    assert (await _bulk(client, w, "check", b"")).status_code in (400, 413, 422)
    nothing = await _bulk(client, w, "check", b"just,one,column\r\n")
    assert nothing.status_code in (400, 422)
    many = _csv(
        *[f"x,{w['centre']},{_day(30)},{_day(60)},1" for _ in range(bulk_module.MAX_ROWS + 1)]
    )
    assert (await _bulk(client, w, "check", many)).status_code in (400, 413, 422)


async def test_published_in_bulk_through_the_single_writer_with_each_refusal_reported(
    client, db, world
):
    w = world
    row = await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    made = (
        await _bulk(
            client,
            w,
            "apply",
            _csv(
                f"{w['course']},{w['centre']},{_day(30)},{_day(60)},10",
                f"{w['course']},{w['centre']},{_day(31)},{_day(61)},10",
            ),
        )
    ).json()
    ids = [r["id"] for r in made["rows"] if r["created"]]
    # One of them is already started by the time the publication runs: the writer refuses it.
    await _set(db, ids[1], starts_on=today_ist() - timedelta(days=1))
    result = await client.post(
        f"/org/{w['partner']}/batches/bulk/publish",
        headers=w["partner_h"],
        json={"ids": [*ids, ids[0], "not-an-id", str(uuid.uuid4())]},
    )
    assert result.status_code == 200, result.text
    got = result.json()
    assert (got["published"], got["refused"]) == (1, 3), "a repeated id is one act"
    by_id = {r["id"]: r for r in got["results"]}
    assert by_id[ids[0]]["published"] is True
    assert "already passed" in by_id[ids[1]]["message"]
    assert by_id["not-an-id"]["message"] == "Batch not found"
    assert (await _row(db, ids[0])).status == "published"
    del row


async def test_publishing_in_bulk_cannot_reach_another_organisations_batch(client, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    draft = await _plan_at(client, w, start=30)
    other_h, other = await _deliverer(client)
    got = (
        await client.post(
            f"/org/{other}/batches/bulk/publish", headers=other_h, json={"ids": [draft]}
        )
    ).json()
    assert got["published"] == 0 and got["results"][0]["message"] == "Batch not found"


async def test_a_file_of_batches_is_for_admins_and_owners_only(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    body = _csv(f"{w['course']},{w['centre']},{_day(30)},{_day(60)},10")
    for verb in ("check", "apply"):
        assert (
            await _bulk(client, w, verb, body, org=w["seller"], headers=w["seller_h"])
        ).status_code == 403
    manager = await _manager(client, db, w["partner_h"], w["partner"], w["centre"])
    for verb in ("check", "apply"):
        refused = await _bulk(client, w, verb, body, org=w["centre"], headers=manager)
        assert refused.status_code in (403, 404)
    assert (await _bulk(client, w, "check", body, org="no-such-org")).status_code == 404
    assert (
        await client.get(f"/org/{w['partner']}/batches/bulk/template", headers=w["partner_h"])
    ).status_code == 200


async def test_a_taken_down_course_needs_a_look_too(client, db, world):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    await _plan_at(client, w, start=30)
    await db.execute(
        update(Course)
        .where(Course.slug == w["course"])
        .values(taken_down_at=datetime.now(UTC), takedown_reason="reported")
    )
    await db.commit()
    got = (await client.get(f"/org/{w['partner']}/batches/overview", headers=w["partner_h"])).json()
    assert got["unavailable"] == 1


async def test_two_rows_of_one_course_and_centre_are_two_batches_when_the_day_or_name_differs(
    client, world
):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    base = f"{w['course']},{w['centre']}"
    body = _csv(
        f"{base},{_day(30)},{_day(60)},10,,Morning",
        f"{base},{_day(30)},{_day(60)},10,,Evening",
        f"{base},{_day(31)},{_day(61)},10,,Morning",
    )
    rows = (await _bulk(client, w, "apply", body)).json()["rows"]
    assert [r["status"] for r in rows] == ["ok", "ok", "ok"]
    assert all(r["created"] for r in rows)


# ================================================================ Sprint 100: the learner's side

from api.core.config import PRIVACY_NOTICE_VERSION as _CONSENT  # noqa: E402
from api.modules.geography.models import District, State  # noqa: E402
from api.modules.matching.attendance import REACH_RANK  # noqa: E402


async def _learner(client, db, name="Asha Rao") -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    """A candidate with a profile, a name and a phone: `(headers, user id, profile id)`."""
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    tokens = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": _CONSENT}
        )
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    user_id = uuid.UUID((await client.get("/auth/me", headers=headers)).json()["id"])
    assert (await client.get("/me/profile", headers=headers)).status_code == 200
    await db.execute(update(User).where(User.id == user_id).values(full_name=name))
    await db.commit()
    profile_id = await db.scalar(
        select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)
    )
    assert profile_id is not None
    return headers, user_id, profile_id


async def _ids(db: AsyncSession, place: tuple[str, str]) -> tuple[uuid.UUID, uuid.UUID]:
    state = await db.scalar(select(State).where(State.name == place[0]))
    district = await db.scalar(select(District).where(District.name == place[1]))
    assert state is not None and district is not None
    return state.id, district.id


async def _lives_in(db: AsyncSession, profile_id: uuid.UUID, place: tuple[str, str]) -> None:
    state_id, district_id = await _ids(db, place)
    await db.execute(
        update(CandidateProfile)
        .where(CandidateProfile.id == profile_id)
        .values(state_id=state_id, district_id=district_id)
    )
    await db.commit()


async def _another_place(db: AsyncSession) -> tuple[str, str]:
    state = State(
        state_code=800_000 + uuid.uuid4().int % 90_000,
        name=f"Otherland {uuid.uuid4().hex[:6]}",
        slug=f"otherland-{uuid.uuid4().hex[:8]}",
    )
    db.add(state)
    await db.flush()
    district = District(
        district_code=800_000 + uuid.uuid4().int % 90_000,
        state_id=state.id,
        name=f"Otherville {uuid.uuid4().hex[:6]}",
        slug=f"otherville-{uuid.uuid4().hex[:8]}",
    )
    db.add(district)
    await db.commit()
    return state.name, district.name


async def _interest_in(client, headers, batch_id, message=None):
    return await client.post(
        "/me/batch-interests", headers=headers, json={"batch_id": batch_id, "message": message}
    )


async def _listed(client, headers=None, **params) -> dict:
    got = await client.get("/batches", headers=headers or {}, params=params)
    assert got.status_code == 200, got.text
    return got.json()


async def _open_world(client, w, *, start=20, seats=10, **over) -> str:
    """One published, joinable batch of the world's course at its centre."""
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"]) if not w.get(
        "approved"
    ) else None
    w["approved"] = True
    batch = await _plan_at(client, w, start=start, seats=seats, **over)
    await _publish(client, w, batch)
    return batch


# ---------------------------------------------------------------- finding a batch


async def test_the_public_list_shows_what_can_still_be_joined_and_nothing_else(client, db, world):
    w = world
    open_id = await _open_world(client, w, start=20, seats=10)
    full_id = await _open_world(client, w, start=21, seats=1)
    await _interest(db, full_id, "enrolled")
    await _plan_at(client, w, start=22)  # a draft
    cancelled = await _open_world(client, w, start=23)
    await client.post(f"/org/{w['partner']}/batches/{cancelled}/cancel", headers=w["partner_h"])
    running = await _open_world(client, w, start=1)
    await _set(db, running, starts_on=today_ist())
    finished = await _open_world(client, w, start=2)
    await _set(
        db,
        finished,
        starts_on=today_ist() - timedelta(days=9),
        ends_on=today_ist() - timedelta(days=1),
    )
    # A batch of a course that stopped being live, and one at a closed centre.
    other_course = await _course(client, w["seller_h"], w["seller"], w["skill"], "Gone course")
    gone = await _open_world(client, w, start=24, course=other_course)
    await db.execute(update(Course).where(Course.slug == other_course).values(status="draft"))
    await db.commit()

    got = await _listed(client)  # signed out
    ids = [b["id"] for b in got["items"]]
    assert set(ids) == {open_id, full_id}, "joinable, and just filled: nothing else"
    assert got["total"] == 2
    by_id = {b["id"]: b for b in got["items"]}
    assert by_id[open_id]["phase"] == "open" and by_id[open_id]["seats_left"] == 10
    assert by_id[full_id]["phase"] == "full" and by_id[full_id]["seats_left"] == 0
    assert gone not in ids


async def test_what_a_learner_is_shown_carries_no_person_and_no_count_of_the_interested(
    client, db, world
):
    w = world
    batch = await _open_world(client, w)
    await _interest(db, batch, "registered")
    await _interest(db, batch, "enrolled")
    row = (await _listed(client))["items"][0]
    assert set(row) == {
        *("id", "course", "centre", "organisation", "label", "starts_on", "ends_on"),
        *("seats", "seats_left", "mode", "schedule", "fee_effective", "fee_is_override"),
        *("phase", "cancel_reason", "reach", "my_interest"),
    }
    assert set(row["centre"]) == {
        "slug",
        "name",
        "location_state",
        "location_district",
        "is_verified",
    }
    text = str(row)
    for secret in ("interested", "enrolled", "phone", "email", "address"):
        assert secret not in text
    assert row["seats_left"] == 9, "the one derived figure: seats minus those the centre enrolled"


async def test_one_batch_by_link_cancelled_is_shown_as_such_and_a_draft_is_not_there(
    client, world, db
):
    w = world
    batch = await _open_world(client, w)
    draft = await _plan_at(client, w, start=40)
    assert (await client.get(f"/batches/{batch}")).json()["phase"] == "open"
    assert (await client.get(f"/batches/{draft}")).status_code == 404
    await client.post(f"/org/{w['partner']}/batches/{batch}/cancel", headers=w["partner_h"])
    gone = (await client.get(f"/batches/{batch}")).json()
    assert gone["phase"] == "cancelled" and gone["cancel_reason"] == "by_organisation"
    assert (await client.get(f"/batches/{uuid.uuid4()}")).status_code == 404
    await db.execute(update(Course).where(Course.slug == w["course"]).values(status="draft"))
    await db.commit()
    assert (await client.get(f"/batches/{batch}")).status_code == 404


async def test_the_order_is_reach_then_soonest_then_cheapest_and_nothing_is_hidden(
    client, db, world, place
):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    w["approved"] = True
    elsewhere = await _another_place(db)
    state_only = (place[0], "Nowhereville")
    centres = {
        "district": w["centre"],
        "state": await _centre(client, w["partner_h"], w["partner"], state_only, "State only"),
        "unknown": await _centre(
            client, w["partner_h"], w["partner"], ("Atlantis", "Lemuria"), "Unknown"
        ),
        "elsewhere": await _centre(client, w["partner_h"], w["partner"], elsewhere, "Far away"),
    }
    made = {}
    for i, (reach, slug) in enumerate(centres.items()):
        # The nearest starts LAST: reach must outrank the date.
        made[reach] = await _plan_at(client, w, start=40 - i * 5, centre=slug)
        await _publish(client, w, made[reach])
    headers, _user, profile_id = await _learner(client, db)
    await _lives_in(db, profile_id, place)

    got = (await _listed(client, headers))["items"]
    assert [b["id"] for b in got] == [
        made["district"],
        made["state"],
        made["unknown"],
        made["elsewhere"],
    ]
    assert [b["reach"] for b in got] == ["district", "state", "unknown", "elsewhere"]
    ranks = [REACH_RANK[b["reach"]] for b in got]
    assert ranks == sorted(ranks), "the label and the order are one rule"
    assert len(got) == 4, "a far batch is last, never gone"


async def test_an_online_batch_is_as_near_as_one_in_your_district(client, db, world, place):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    w["approved"] = True
    far = await _another_place(db)
    far_centre = await _centre(client, w["partner_h"], w["partner"], far, "Far centre")
    online = await _plan_at(client, w, start=30, centre=far_centre, mode="online")
    await _publish(client, w, online)
    here = await _plan_at(client, w, start=40)
    await _publish(client, w, here)
    headers, _user, profile_id = await _learner(client, db)
    await _lives_in(db, profile_id, place)
    got = (await _listed(client, headers))["items"]
    assert [b["reach"] for b in got] == ["online", "district"]
    assert [b["id"] for b in got] == [online, here], "equal reach: the sooner first"


async def test_the_same_reach_orders_by_start_then_by_the_fee_the_learner_would_pay(
    client, db, world
):
    w = world
    sooner = await _open_world(client, w, start=20)
    dear = await _open_world(client, w, start=30, fee_inr=9000)
    cheap = await _open_world(client, w, start=30, fee_inr=1000)
    free = await _open_world(client, w, start=30, fee_inr=0)
    got = [b["id"] for b in (await _listed(client))["items"]]
    assert got == [sooner, free, cheap, dear]
    assert {b["id"]: b["fee_is_override"] for b in (await _listed(client))["items"]}[dear] is True


async def test_an_anonymous_visitor_can_say_where_they_are_and_it_filters_and_orders(
    client, db, world, place
):
    w = world
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    w["approved"] = True
    far = await _another_place(db)
    far_centre = await _centre(client, w["partner_h"], w["partner"], far, "Far centre")
    near = await _plan_at(client, w, start=30)
    await _publish(client, w, near)
    away = await _plan_at(client, w, start=25, centre=far_centre)
    await _publish(client, w, away)
    state_id, district_id = await _ids(db, place)
    everyone = await _listed(client)
    assert {b["reach"] for b in everyone["items"]} <= {"unknown"}, "no evidence about the person"
    here = await _listed(client, district_id=str(district_id))
    assert [b["id"] for b in here["items"]] == [near] and here["items"][0]["reach"] == "district"
    in_state = await _listed(client, state_id=str(state_id))
    assert [b["id"] for b in in_state["items"]] == [near]


async def test_filters_total_and_paging(client, db, world):
    w = world
    soon = await _open_world(client, w, start=5)
    later = await _open_world(client, w, start=60, fee_inr=8000)
    other_course = await _course(client, w["seller_h"], w["seller"], w["skill"], "Other course")
    other = await _open_world(client, w, start=10, course=other_course, mode="online")

    assert [b["id"] for b in (await _listed(client, starts_within=14))["items"]] == [other, soon]
    assert [b["id"] for b in (await _listed(client, max_fee=5000))["items"]] == [other, soon]
    assert [b["id"] for b in (await _listed(client, course=other_course))["items"]] == [other]
    assert [b["id"] for b in (await _listed(client, mode="online"))["items"]] == [other]
    first = await _listed(client, limit=2)
    second = await _listed(client, limit=2, offset=2)
    assert first["total"] == second["total"] == 3, "the count of what matches, not the page"
    assert [b["id"] for b in first["items"] + second["items"]] == [other, soon, later], (
        "an online batch is as near as one in your district: it comes first, then by start"
    )
    assert (await client.get("/batches", params={"starts_within": 0})).status_code == 422
    assert (await client.get("/batches", params={"mode": "teleport"})).status_code == 422


# ---------------------------------------------------------------- registering and withdrawing


async def test_a_learner_registers_the_centre_is_told_and_they_can_take_it_back(client, db, world):
    w = world
    batch = await _open_world(client, w)
    headers, user_id, profile_id = await _learner(client, db)

    made = await _interest_in(client, headers, batch, "Evenings only, please")
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["status"] == "registered" and body["message"] == "Evenings only, please"
    assert body["batch"]["id"] == batch
    row = await db.scalar(select(BatchInterest).where(BatchInterest.profile_id == profile_id))
    assert row is not None and row.contact_shared_at is not None and row.contact_revoked_at is None
    # The organisation is told once, by email, with a name and a link and nobody's details.
    org = await _tenant(db, w["partner"])
    mail = (
        await db.scalars(
            select(Notification).where(
                Notification.recipient_id == org.id,
                Notification.template == "batch_interest_registered",
            )
        )
    ).all()
    assert len(mail) == 1 and mail[0].channel == "email"
    assert set(mail[0].payload) == {"course", "centre", "path"}
    assert mail[0].payload["path"] == f"/employer/{w['partner']}/batches"
    event = await db.scalar(
        select(AnalyticsEvent).where(AnalyticsEvent.name == "batch_interest_registered")
    )
    assert event is not None and set(event.payload) == {"organisation", "provider"}

    listed = (await _listed(client, headers))["items"][0]
    assert listed["my_interest"] == {"id": body["id"], "status": "registered"}
    assert (await client.get(f"/batches/{batch}", headers=headers)).json()["my_interest"][
        "id"
    ] == body["id"]
    assert (await _listed(client))["items"][0]["my_interest"] is None, "signed out: nobody's"

    again = await _interest_in(client, headers, batch)
    assert again.status_code == 409

    back = await client.post(f"/me/batch-interests/{body['id']}/withdraw", headers=headers)
    assert back.status_code == 200 and back.json()["status"] == "withdrawn"
    await db.refresh(row)
    assert row.contact_revoked_at is not None
    assert (await _listed(client, headers))["items"][0]["my_interest"] is None
    # Changing their mind is not an error: the same row is reused.
    once_more = await _interest_in(client, headers, batch)
    assert once_more.status_code == 201 and once_more.json()["id"] == body["id"]
    count = await db.scalar(
        select(func.count())
        .select_from(BatchInterest)
        .where(BatchInterest.profile_id == profile_id)
    )
    assert count == 1


async def test_a_batch_that_cannot_be_joined_is_refused_for_the_right_reason(client, db, world):
    w = world
    full = await _open_world(client, w, start=20, seats=1)
    await _interest(db, full, "enrolled")
    running = await _open_world(client, w, start=3)
    await _set(db, running, starts_on=today_ist())
    draft = await _plan_at(client, w, start=40)
    cancelled = await _open_world(client, w, start=30)
    await client.post(f"/org/{w['partner']}/batches/{cancelled}/cancel", headers=w["partner_h"])
    headers, _user, _profile = await _learner(client, db)
    assert (await _interest_in(client, headers, full)).status_code == 409
    assert "full" in (await _interest_in(client, headers, full)).json()["detail"]
    assert "started" in (await _interest_in(client, headers, running)).json()["detail"]
    for gone in (draft, cancelled, str(uuid.uuid4()), "not-an-id"):
        assert (await _interest_in(client, headers, gone)).status_code == 404, gone


async def test_a_learner_whose_course_stopped_being_live_cannot_register(client, db, world):
    w = world
    batch = await _open_world(client, w)
    await db.execute(update(Course).where(Course.slug == w["course"]).values(status="draft"))
    await db.commit()
    headers, _u, _p = await _learner(client, db)
    assert (await _interest_in(client, headers, batch)).status_code == 404


async def test_a_paused_learner_cannot_register_and_pausing_takes_back_what_was_shared(
    client, db, world
):
    w = world
    batch = await _open_world(client, w)
    headers, _user, profile_id = await _learner(client, db)
    made = (await _interest_in(client, headers, batch)).json()
    paused = await client.post("/me/account/consent/withdraw", headers=headers)
    assert paused.status_code == 200, paused.text
    row = await db.scalar(
        select(BatchInterest)
        .where(BatchInterest.id == uuid.UUID(made["id"]))
        .execution_options(populate_existing=True)
    )
    assert row is not None and row.status == "withdrawn" and row.contact_revoked_at is not None
    other = await _open_world(client, w, start=45)
    refused = await _interest_in(client, headers, other)
    assert refused.status_code == 409, "a disclosure is stopped outright while consent is withdrawn"
    assert (
        "paused" in refused.json()["detail"].lower()
        or "consent" in refused.json()["detail"].lower()
    )
    assert profile_id


async def test_an_organisation_only_account_cannot_register_and_is_given_no_profile(
    client, db, world
):
    w = world
    batch = await _open_world(client, w)
    before = await db.scalar(select(func.count()).select_from(CandidateProfile))
    org_h, _org = await _register(client, f"Only Org {uuid.uuid4().hex[:6]}", sells=True)
    refused = await _interest_in(client, org_h, batch)
    assert refused.status_code in (403, 404)
    # ...and merely reading the public list does not create one either.
    assert (await client.get("/batches", headers=org_h)).status_code == 200
    assert await db.scalar(select(func.count()).select_from(CandidateProfile)) == before


async def test_the_daily_limit_applies_to_batches_too(client, db, world, monkeypatch):
    from api.core.config import get_settings

    w = world
    first = await _open_world(client, w, start=20)
    second = await _open_world(client, w, start=21)
    headers, _u, _p = await _learner(client, db)
    monkeypatch.setattr(get_settings(), "max_course_interests_per_day", 1)
    assert (await _interest_in(client, headers, first)).status_code == 201
    limited = await _interest_in(client, headers, second)
    assert limited.status_code == 429 and limited.headers["retry-after"] == "3600"


async def test_my_interests_show_a_cancelled_batch_and_are_nobody_elses(client, db, world):
    w = world
    batch = await _open_world(client, w)
    headers, _u, _p = await _learner(client, db)
    other_headers, _ou, _op = await _learner(client, db, "Ravi Iyer")
    made = (await _interest_in(client, headers, batch)).json()
    await client.post(f"/org/{w['partner']}/batches/{batch}/cancel", headers=w["partner_h"])
    mine = (await client.get("/me/batch-interests", headers=headers)).json()
    assert [(i["id"], i["batch"]["phase"], i["batch"]["cancel_reason"]) for i in mine] == [
        (made["id"], "cancelled", "by_organisation")
    ]
    assert (await client.get("/me/batch-interests", headers=other_headers)).json() == []
    stranger = await client.post(
        f"/me/batch-interests/{made['id']}/withdraw", headers=other_headers
    )
    assert stranger.status_code == 404
    gone = (await client.get("/me/batch-interests", headers=headers)).json()[0]
    assert gone["status"] == "registered", "a stranger's attempt changed nothing"


# ---------------------------------------------------------------- the centre sees them


async def _registered(client, db, batch, n=1, message=None):
    people = []
    for i in range(n):
        h, uid, pid = await _learner(client, db, f"Learner {i}")
        made = await _interest_in(client, h, batch, message)
        assert made.status_code == 201, made.text
        people.append((h, uid, pid, made.json()["id"]))
    return people


async def test_the_organisation_sees_who_registered_unanswered_first_and_oldest_first(
    client, db, world
):
    w = world
    batch = await _open_world(client, w)
    first, second, third = await _registered(client, db, batch, 3, "Hello")
    for person in (second, third):
        await db.execute(
            update(CandidateProfile)
            .where(CandidateProfile.id == person[2])
            .values(location_state="Maharashtra", location_district="Pune")
        )
    await db.commit()
    # The suite is one transaction, so `now()` is the same instant for all three: say who was first.
    for age, person in zip((3, 2, 1), (first, second, third), strict=True):
        await db.execute(
            update(BatchInterest)
            .where(BatchInterest.id == uuid.UUID(person[3]))
            .values(created_at=datetime.now(UTC) - timedelta(days=age))
        )
    await db.flush()
    # The oldest has been answered; the order puts the still-waiting ones first, longest first.
    await client.patch(
        f"/org/{w['partner']}/batches/{batch}/learners/{first[3]}",
        headers=w["partner_h"],
        json={"status": "contacted"},
    )
    await client.post(f"/me/batch-interests/{third[3]}/withdraw", headers=third[0])
    got = (
        await client.get(f"/org/{w['partner']}/batches/{batch}/learners", headers=w["partner_h"])
    ).json()
    assert [i["interest_id"] for i in got["items"]] == [second[3], first[3], third[3]]
    waiting, answered, withdrawn = got["items"]
    assert waiting["contact"]["full_name"] == "Learner 1" and waiting["contact"]["phone"]
    assert waiting["message"] == "Hello"
    assert (waiting["location_state"], waiting["location_district"]) == ("Maharashtra", "Pune")
    assert answered["status"] == "contacted"
    # Withdrawn keeps the fact and loses the person.
    assert withdrawn["status"] == "withdrawn"
    assert withdrawn["contact"] is None and withdrawn["message"] is None
    assert withdrawn["location_district"] is None
    assert got["batch"]["interested"] == 2, "the withdrawn one is not counted as interested"


async def test_who_may_see_a_learner_is_the_centre_and_its_organisations_owners_and_admins(
    client, db, world
):
    w = world
    sibling = await _centre(client, w["partner_h"], w["partner"], w["place"], "Kothrud")
    await _approve_all(client, w["seller_h"], w["seller"], w["partner"])
    w["approved"] = True
    here = await _open_world(client, w)
    there = await _plan_at(client, w, start=30, centre=sibling)
    await _publish(client, w, there)
    await _registered(client, db, here)
    await _registered(client, db, there)
    path = lambda org, b: f"/org/{org}/batches/{b}/learners"  # noqa: E731

    assert (await client.get(path(w["partner"], here), headers=w["partner_h"])).status_code == 200
    manager = await _manager(client, db, w["partner_h"], w["partner"], w["centre"])
    assert (await client.get(path(w["centre"], here), headers=manager)).status_code == 200
    # Their own centre only: a sibling's learners are the 404 of none.
    assert (await client.get(path(w["centre"], there), headers=manager)).status_code == 404
    # The seller of the course never reaches a learner, by any door.
    for org, headers in ((w["seller"], w["seller_h"]), (w["partner"], w["seller_h"])):
        refused = await client.get(path(org, here), headers=headers)
        assert refused.status_code in (403, 404)
    # A plain member reads the batch and never a person.
    from api.modules.identity.models import Membership

    tenant = await _tenant(db, w["partner"])
    owner = await db.scalar(select(Membership).where(Membership.tenant_id == tenant.id))
    assert owner is not None
    owner.role = "member"
    await db.commit()
    assert (
        await client.get(f"/org/{w['partner']}/batches/{here}", headers=w["partner_h"])
    ).status_code == 200
    assert (await client.get(path(w["partner"], here), headers=w["partner_h"])).status_code == 403
    # ...and another organisation gets the 404 of a batch that does not exist.
    other_h, other = await _deliverer(client)
    assert (await client.get(path(other, here), headers=other_h)).status_code == 404


async def test_marking_a_learner_tells_them_and_enrolling_takes_a_seat(client, db, world):
    w = world
    batch = await _open_world(client, w, seats=2)
    (h1, u1, _p1, i1), (h2, u2, _p2, i2), (h3, _u3, _p3, i3) = await _registered(
        client, db, batch, 3
    )
    mark = lambda interest, status: client.patch(  # noqa: E731
        f"/org/{w['partner']}/batches/{batch}/learners/{interest}",
        headers=w["partner_h"],
        json={"status": status},
    )
    contacted = await mark(i1, "contacted")
    assert contacted.status_code == 200
    notices = (
        await db.scalars(
            select(Notification).where(
                Notification.recipient_id == u1,
                Notification.template == "batch_interest_status_changed",
            )
        )
    ).all()
    assert len(notices) == 1 and notices[0].channel == "in_app"
    assert set(notices[0].payload) == {"course", "organisation", "status", "path"}
    assert notices[0].payload["status"] == "contacted"
    await mark(i1, "contacted")  # unchanged: nobody is told twice
    assert (
        len(
            (
                await db.scalars(
                    select(Notification).where(
                        Notification.recipient_id == u1,
                        Notification.template == "batch_interest_status_changed",
                    )
                )
            ).all()
        )
        == 1
    )

    assert (await mark(i1, "enrolled")).status_code == 200
    assert (await mark(i2, "enrolled")).status_code == 200
    assert (await _listed(client))["items"][0]["seats_left"] == 0
    full = await mark(i3, "enrolled")
    assert full.status_code == 409 and "Every seat is taken" in full.json()["detail"]
    # Someone enrolled can be moved to contacted again (a correction), which frees the seat.
    assert (await mark(i2, "contacted")).status_code == 200
    assert (await mark(i3, "enrolled")).status_code == 200
    assert (await _listed(client))["items"][0]["seats_left"] == 0
    assert u2 and h1 and h2 and h3


async def test_attended_needs_a_started_batch_and_an_enrolled_learner_and_still_holds_the_seat(
    client, db, world
):
    w = world
    batch = await _open_world(client, w, seats=1)
    ((_h, _u, _p, interest),) = await _registered(client, db, batch)
    url = f"/org/{w['partner']}/batches/{batch}/learners/{interest}"
    attend = lambda: client.patch(url, headers=w["partner_h"], json={"status": "attended"})  # noqa: E731
    not_yet = await attend()
    assert not_yet.status_code == 409 and "enrolled before" in not_yet.json()["detail"], (
        "not enrolled yet, and that is the reason it says"
    )
    await client.patch(url, headers=w["partner_h"], json={"status": "enrolled"})
    early = await attend()
    assert early.status_code == 409 and "has not started" in early.json()["detail"]
    await _set(db, batch, starts_on=today_ist())
    done = await attend()
    assert done.status_code == 200
    assert done.json()["items"][0]["status"] == "attended"
    assert done.json()["batch"]["seats_left"] == 0, "a learner who came still holds the seat"
    assert (
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.template == "batch_interest_status_changed",
                Notification.payload["status"].astext == "attended",
            )
        )
    ) == 0, "no notice for attending"


async def test_a_withdrawn_or_foreign_interest_cannot_be_moved_and_a_cancelled_batch_is_closed(
    client, db, world
):
    w = world
    batch = await _open_world(client, w)
    other = await _open_world(client, w, start=40)
    ((h, _u, _p, interest),) = await _registered(client, db, batch)
    ((_h2, _u2, _p2, elsewhere),) = await _registered(client, db, other)
    url = lambda b, i: f"/org/{w['partner']}/batches/{b}/learners/{i}"  # noqa: E731
    body = {"status": "contacted"}
    assert (
        await client.patch(url(batch, elsewhere), headers=w["partner_h"], json=body)
    ).status_code == 404
    assert (
        await client.patch(url(batch, uuid.uuid4()), headers=w["partner_h"], json=body)
    ).status_code == 404
    assert (
        await client.patch(
            url(batch, interest), headers=w["partner_h"], json={"status": "registered"}
        )
    ).status_code == 422
    assert (
        await client.patch(
            url(batch, interest), headers=w["partner_h"], json={"status": "withdrawn"}
        )
    ).status_code == 422
    await client.post(f"/me/batch-interests/{interest}/withdraw", headers=h)
    refused = await client.patch(url(batch, interest), headers=w["partner_h"], json=body)
    assert refused.status_code == 409 and "withdrawn" in refused.json()["detail"]
    await client.post(f"/org/{w['partner']}/batches/{other}/cancel", headers=w["partner_h"])
    assert (
        await client.patch(url(other, elsewhere), headers=w["partner_h"], json=body)
    ).status_code == 409


async def test_replies_owed_is_counted_per_scope_and_leaves_when_answered(client, db, world):
    w = world
    batch = await _open_world(client, w)
    (_h, _u, _p, first), (_h2, _u2, _p2, _second) = await _registered(client, db, batch, 2)
    overview = lambda: client.get(f"/org/{w['partner']}/batches/overview", headers=w["partner_h"])  # noqa: E731
    got = (await overview()).json()
    assert got["replies_owed"] == 2 and got["oldest_reply_owed_since"] is not None
    await client.patch(
        f"/org/{w['partner']}/batches/{batch}/learners/{first}",
        headers=w["partner_h"],
        json={"status": "contacted"},
    )
    assert (await overview()).json()["replies_owed"] == 1
    other_h, other = await _deliverer(client)
    assert (await client.get(f"/org/{other}/batches/overview", headers=other_h)).json()[
        "replies_owed"
    ] == 0


# ---------------------------------------------------------------- the person's own record


async def test_the_export_names_the_batch_the_centre_and_what_was_shared_and_erasure_removes_it(
    client, db, world
):
    w = world
    batch = await _open_world(client, w)
    headers, user_id, profile_id = await _learner(client, db)
    await _interest_in(client, headers, batch, "Mornings")
    exported = (await client.get("/me/account/export", headers=headers)).json()
    rows = exported["batch_interests"]
    assert len(rows) == 1
    assert rows[0]["course"] == "Welding basics"
    assert rows[0]["centre"] and rows[0]["organisation"]
    assert (
        rows[0]["message"] == "Mornings"
        and rows[0]["contact_shared_at"]
        and rows[0]["contact_revoked_at"] is None
    )
    assert "profile_id" not in str(rows) and str(user_id) not in str(rows)

    gone = await client.delete("/me/account", headers=headers)
    assert gone.status_code in (200, 204), gone.text
    assert (
        await db.scalar(
            select(func.count())
            .select_from(BatchInterest)
            .where(BatchInterest.profile_id == profile_id)
        )
    ) == 0


# ------------------------------------------------- defensive states the writers refuse (forced)


async def test_a_batch_whose_course_was_taken_down_is_not_listed_and_cannot_be_registered_for(
    client, db, world
):
    """A takedown does not cancel batches (the card warns, publication refuses): the learner's
    doors are what close. Forced into the state, because no writer of a batch will create it."""
    w = world
    batch = await _open_world(client, w)
    headers, _, _ = await _learner(client, db)
    assert [b["id"] for b in (await _listed(client))["items"]] == [batch]
    await db.execute(
        update(Course)
        .where(Course.slug == w["course"])
        .values(taken_down_at=datetime.now(UTC), takedown_reason="Reported")
    )
    await db.commit()
    assert (await _listed(client))["items"] == []
    assert (await client.get(f"/batches/{batch}")).status_code == 404
    refused = await _interest_in(client, headers, batch)
    assert refused.status_code == 404, refused.text


async def test_a_batch_at_a_closed_centre_is_not_listed_and_cannot_be_registered_for(
    client, db, world
):
    w = world
    batch = await _open_world(client, w)
    headers, _, _ = await _learner(client, db)
    await db.execute(
        update(Tenant).where(Tenant.slug == w["centre"]).values(closed_at=datetime.now(UTC))
    )
    await db.commit()
    assert (await _listed(client))["items"] == []
    assert (await client.get(f"/batches/{batch}")).status_code == 404
    refused = await _interest_in(client, headers, batch)
    assert refused.status_code == 409 and "closed" in refused.json()["detail"], refused.text


async def test_batches_that_tie_on_everything_page_without_repeating_or_skipping(client, db, world):
    w = world
    made = {await _open_world(client, w, start=30, seats=5) for _ in range(5)}
    assert len(made) == 5
    seen: list[str] = []
    for offset in range(5):
        page = await _listed(client, limit=1, offset=offset)
        assert page["total"] == 5
        seen += [b["id"] for b in page["items"]]
    assert sorted(seen) == sorted(made), "each exactly once across the pages"


async def test_registering_again_after_withdrawing_brings_the_contact_back_on_the_same_row(
    client, db, world
):
    w = world
    batch = await _open_world(client, w)
    headers, _, profile_id = await _learner(client, db)
    first = (await _interest_in(client, headers, batch)).json()
    await client.post(f"/me/batch-interests/{first['id']}/withdraw", headers=headers)
    row = await db.scalar(
        select(BatchInterest)
        .where(BatchInterest.profile_id == profile_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None and row.contact_revoked_at is not None, "withdrawing takes it back"
    again = await _interest_in(client, headers, batch)
    assert again.status_code == 201 and again.json()["id"] == first["id"], "the same row"
    row = await db.scalar(
        select(BatchInterest)
        .where(BatchInterest.profile_id == profile_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None and row.status == "registered"
    assert row.contact_revoked_at is None and row.contact_shared_at is not None
