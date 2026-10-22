"""A course has a place, a next intake and a number of seats (Sprint 58, BL-14.5, ADR-068).

`courses_closing_gap` recommended an offline course in another state exactly as it recommended one
next door, because a course had no place at all. These pin what the data now says: where, when,
how many places and how many are left -- and that the last is **derived** from the learners a
provider has marked enrolled, never a stored counter that drifts.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import today_ist
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.geography.models import District, State
from api.modules.identity import Tenant
from api.modules.identity.models import User
from api.modules.interests import CourseInterest, enrolled_counts
from api.modules.marketplace.models import CandidateProfile, Course
from api.modules.skills.models import Skill


@pytest.fixture
async def skill(db: AsyncSession) -> str:
    row = Skill(
        slug=f"place-skill-{uuid.uuid4().hex[:8]}",
        name="Apply sterile technique",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="PLC/N0101",
        source="nsqf",
    )
    db.add(row)
    await db.commit()
    return row.slug


@pytest.fixture
async def master(db: AsyncSession) -> dict[str, District]:
    suffix = uuid.uuid4().int % 90_000 + 1000
    state = State(state_code=suffix, slug=f"st-{suffix}", name=f"Placeland{suffix}")
    db.add(state)
    await db.flush()
    pune = District(district_code=suffix * 10, name=f"Punetown{suffix}", state_id=state.id)
    db.add(pune)
    await db.commit()
    return {"state": state, "district": pune}  # type: ignore[dict-item]


async def _provider(client: AsyncClient, db: AsyncSession) -> tuple[dict[str, str], str]:
    address = f"provider-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"
    requested = await client.post(
        "/auth/org/register",
        json={
            "email": address,
            "organisation_name": f"Place Academy {uuid.uuid4().hex[:6]}",
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
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == slug))
    assert tenant is not None
    tenant.tenant_type = "course_provider"
    tenant.publishes_courses = True  # a provider sells courses (Sprint 94, ADR-102)
    await db.commit()
    return headers, slug


def _body(skill: str, **over: object) -> dict[str, object]:
    return {
        "title": "Sterile Technique for Ward Staff",
        "mode": "offline",
        "skills": [{"skill_slug": skill, "level_taught": 4}],
        **over,
    }


async def _publish(client: AsyncClient, headers: dict[str, str], org: str, slug: str) -> None:
    assert (
        await client.post(f"/org/{org}/courses/{slug}/publish", headers=headers)
    ).status_code == 200


async def _enrol(db: AsyncSession, course_id: uuid.UUID, status: str) -> None:
    user = User(phone=f"+91{9000000000 + uuid.uuid4().int % 999_999_999}")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(user_id=user.id)
    db.add(profile)
    await db.flush()
    db.add(CourseInterest(course_id=course_id, profile_id=profile.id, status=status))
    await db.commit()


class TestAPlaceOnAWrite:
    async def test_a_written_place_is_resolved_beside_the_text(
        self, client: AsyncClient, db: AsyncSession, skill: str, master: dict[str, District]
    ) -> None:
        headers, org = await _provider(client, db)
        state, district = master["state"], master["district"]
        created = await client.post(
            f"/org/{org}/courses",
            headers=headers,
            json=_body(
                skill,
                location_state=state.name,
                location_district=district.name,
                starts_on="2099-01-15",
                seats=30,
            ),
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert (body["location_state"], body["location_district"]) == (state.name, district.name)
        assert (body["starts_on"], body["seats"], body["started"]) == ("2099-01-15", 30, False)
        row = await db.scalar(select(Course).where(Course.slug == body["slug"]))
        assert row is not None
        assert (row.state_id, row.district_id) == (state.id, district.id)

    async def test_a_place_that_does_not_resolve_is_kept_as_typed_with_no_id(
        self, client: AsyncClient, db: AsyncSession, skill: str
    ) -> None:
        headers, org = await _provider(client, db)
        created = await client.post(
            f"/org/{org}/courses",
            headers=headers,
            json=_body(skill, location_state="Nowhere", location_district="Atlantis"),
        )
        assert created.status_code == 201
        row = await db.scalar(select(Course).where(Course.slug == created.json()["slug"]))
        assert row is not None
        assert row.location_district == "Atlantis"
        assert row.state_id is None and row.district_id is None

    async def test_a_course_with_no_place_is_still_valid(
        self, client: AsyncClient, db: AsyncSession, skill: str
    ) -> None:
        headers, org = await _provider(client, db)
        created = await client.post(
            f"/org/{org}/courses", headers=headers, json=_body(skill, mode="online")
        )
        body = created.json()
        assert created.status_code == 201
        assert body["location_state"] is None and body["starts_on"] is None
        assert body["seats"] is None and body["seats_left"] is None and body["started"] is False

    async def test_an_update_moves_the_place_and_the_ids_with_it(
        self, client: AsyncClient, db: AsyncSession, skill: str, master: dict[str, District]
    ) -> None:
        headers, org = await _provider(client, db)
        slug = (
            await client.post(
                f"/org/{org}/courses",
                headers=headers,
                json=_body(skill, location_district="Atlantis"),
            )
        ).json()["slug"]
        state, district = master["state"], master["district"]
        updated = await client.put(
            f"/org/{org}/courses/{slug}",
            headers=headers,
            json=_body(skill, location_state=state.name, location_district=district.name),
        )
        assert updated.status_code == 200
        row = await db.scalar(select(Course).where(Course.slug == slug))
        assert row is not None
        await db.refresh(row)
        assert row.district_id == district.id

    async def test_a_refused_update_changes_nothing_not_even_the_place(
        self, client: AsyncClient, db: AsyncSession, skill: str, master: dict[str, District]
    ) -> None:
        """Anything that can refuse runs before anything is changed (Sprint 55)."""
        headers, org = await _provider(client, db)
        slug = (
            await client.post(
                f"/org/{org}/courses",
                headers=headers,
                json=_body(skill, location_district="Atlantis", seats=5),
            )
        ).json()["slug"]
        refused = await client.put(
            f"/org/{org}/courses/{slug}",
            headers=headers,
            json={
                **_body(skill, location_district=master["district"].name, seats=99),
                "skills": [{"skill_slug": "no-such-standard"}],
            },
        )
        assert refused.status_code in (404, 422)
        shown = (await client.get(f"/org/{org}/courses/{slug}", headers=headers)).json()
        assert (shown["location_district"], shown["seats"]) == ("Atlantis", 5)

    @pytest.mark.parametrize("seats", [0, -3, 100_001])
    async def test_seats_have_a_floor_and_a_ceiling(
        self, client: AsyncClient, db: AsyncSession, skill: str, seats: int
    ) -> None:
        headers, org = await _provider(client, db)
        response = await client.post(
            f"/org/{org}/courses", headers=headers, json=_body(skill, seats=seats)
        )
        assert response.status_code == 422

    async def test_the_database_holds_the_same_floor_without_the_service(
        self, db: AsyncSession
    ) -> None:
        tenant = Tenant(slug=f"t-{uuid.uuid4().hex[:8]}", name="T", tenant_type="course_provider")
        db.add(tenant)
        await db.flush()
        db.add(Course(slug=f"c-{uuid.uuid4().hex[:8]}", tenant_id=tenant.id, title="X", seats=0))
        with pytest.raises(IntegrityError):
            await db.flush()


class TestStarted:
    @pytest.mark.parametrize(
        ("offset_days", "started"), [(-1, True), (0, False), (1, False), (None, False)]
    )
    async def test_started_is_derived_from_the_date_in_india(
        self,
        client: AsyncClient,
        db: AsyncSession,
        skill: str,
        offset_days: int | None,
        started: bool,
    ) -> None:
        headers, org = await _provider(client, db)
        starts = (
            None if offset_days is None else (today_ist() + timedelta(days=offset_days)).isoformat()
        )
        created = await client.post(
            f"/org/{org}/courses", headers=headers, json=_body(skill, starts_on=starts)
        )
        assert created.json()["started"] is started


class TestSeatsAreDerived:
    async def _course(
        self, client: AsyncClient, db: AsyncSession, skill: str, **over: object
    ) -> tuple[dict[str, str], str, str]:
        headers, org = await _provider(client, db)
        slug = (
            await client.post(f"/org/{org}/courses", headers=headers, json=_body(skill, **over))
        ).json()["slug"]
        await _publish(client, headers, org, slug)
        return headers, org, slug

    async def _id(self, db: AsyncSession, slug: str) -> uuid.UUID:
        row = await db.scalar(select(Course).where(Course.slug == slug))
        assert row is not None
        return row.id

    async def test_seats_left_counts_only_the_enrolled(
        self, client: AsyncClient, db: AsyncSession, skill: str
    ) -> None:
        _, _, slug = await self._course(client, db, skill, seats=10)
        course_id = await self._id(db, slug)
        for status in ("enrolled", "enrolled", "registered", "contacted", "withdrawn"):
            await _enrol(db, course_id, status)
        assert (await client.get(f"/courses/{slug}")).json()["seats_left"] == 8

    async def test_seats_left_is_never_negative(
        self, client: AsyncClient, db: AsyncSession, skill: str
    ) -> None:
        _, _, slug = await self._course(client, db, skill, seats=1)
        course_id = await self._id(db, slug)
        await _enrol(db, course_id, "enrolled")
        await _enrol(db, course_id, "enrolled")
        assert (await client.get(f"/courses/{slug}")).json()["seats_left"] == 0

    async def test_no_seat_count_means_no_seats_left_figure(
        self, client: AsyncClient, db: AsyncSession, skill: str
    ) -> None:
        _, _, slug = await self._course(client, db, skill)
        await _enrol(db, await self._id(db, slug), "enrolled")
        body = (await client.get(f"/courses/{slug}")).json()
        assert body["seats"] is None and body["seats_left"] is None

    async def test_a_seat_comes_back_when_somebody_is_no_longer_enrolled(
        self, client: AsyncClient, db: AsyncSession, skill: str
    ) -> None:
        """The reason it is derived: a stored counter would not know."""
        _, _, slug = await self._course(client, db, skill, seats=2)
        course_id = await self._id(db, slug)
        await _enrol(db, course_id, "enrolled")
        assert (await client.get(f"/courses/{slug}")).json()["seats_left"] == 1
        interest = await db.scalar(
            select(CourseInterest).where(CourseInterest.course_id == course_id)
        )
        assert interest is not None
        interest.status = "withdrawn"
        await db.commit()
        assert (await client.get(f"/courses/{slug}")).json()["seats_left"] == 2

    async def test_the_providers_own_list_shows_seats_left_too(
        self, client: AsyncClient, db: AsyncSession, skill: str
    ) -> None:
        headers, org, slug = await self._course(client, db, skill, seats=4)
        await _enrol(db, await self._id(db, slug), "enrolled")
        listed = (await client.get(f"/org/{org}/courses", headers=headers)).json()
        assert [c["seats_left"] for c in listed if c["slug"] == slug] == [3]

    async def test_enrolled_counts_is_empty_for_no_courses_and_omits_unenrolled_ones(
        self, db: AsyncSession
    ) -> None:
        assert await enrolled_counts(db, []) == {}
        assert await enrolled_counts(db, [uuid.uuid4()]) == {}
