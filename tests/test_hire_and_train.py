"""Sprint 41, ADR-048: an employer offers to sponsor the one standard a near-miss
candidate lacks.

The rules worth proving are the ones that protect the candidate. The employer
reaches a candidate only through the de-identified reference the console already
shows; that reference is resolved inside the vacancy's own near-miss pool and
nowhere else; an opted-out or capped candidate is not messaged and the employer
cannot tell; and an offer is made once.
"""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.alerts import SponsorIntent
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import Tenant
from api.modules.marketplace.models import Course, CourseSkill, Job
from api.modules.notifications.models import Notification
from api.modules.skills import Skill


async def _skill(db: AsyncSession, slug: str, code: str) -> Skill:
    skill = Skill(
        slug=slug,
        name=f"Standard {slug}",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code=code,
        source="nsqf",
    )
    db.add(skill)
    await db.flush()
    return skill


async def _candidate(client: AsyncClient, skills: list[str]) -> dict[str, str]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    headers = {"authorization": f"Bearer {body['access_token']}"}
    for slug in skills:
        added = await client.post(
            "/me/profile/skills", headers=headers, json={"skill_slug": slug, "proficiency": 4}
        )
        assert added.status_code in (200, 201), added.text
    return headers


async def _employer(client: AsyncClient, name: str = "Train Co") -> tuple[dict[str, str], str]:
    address = f"train-{uuid.uuid4().hex[:8]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": name,
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    return {"authorization": f"Bearer {tokens['access_token']}"}, tokens["organisation_slug"]


@pytest.fixture
async def stage(client: AsyncClient, db: AsyncSession) -> dict:
    """A vacancy needing three standards; a candidate holding all three, one
    holding two (one short), and one holding only one (two short). A course
    teaches the standard the middle one lacks."""
    a = await _skill(db, "ht-a", "HT/N0001")
    b = await _skill(db, "ht-b", "HT/N0002")
    c = await _skill(db, "ht-c", "HT/N0003")

    provider = Tenant(slug="ht-academy", name="HT Academy", tenant_type="course_provider")
    db.add(provider)
    await db.flush()
    course = Course(
        slug="ht-course-c",
        tenant_id=provider.id,
        title="Course C",
        mode="online",
        status="published",
    )
    db.add(course)
    await db.flush()
    db.add(CourseSkill(course_id=course.id, skill_id=c.id, level_taught=4))
    await db.commit()

    employer, org = await _employer(client)
    job = (
        await client.post(
            f"/org/{org}/jobs",
            headers=employer,
            json={
                "title": "Ward Attendant",
                "skills": [
                    {"skill_slug": s.slug, "importance": 4, "is_mandatory": True} for s in (a, b, c)
                ],
            },
        )
    ).json()
    await client.post(f"/org/{org}/jobs/{job['slug']}/publish", headers=employer)

    ready = await _candidate(client, ["ht-a", "ht-b", "ht-c"])
    near = await _candidate(client, ["ht-a", "ht-b"])
    far = await _candidate(client, ["ht-a"])

    ranking = (await client.get(f"/org/{org}/candidates/{job['slug']}", headers=employer)).json()
    by_missing = {item["missing_mandatory"]: item["reference"] for item in ranking["items"]}
    return {
        "employer": employer,
        "org": org,
        "job": job["slug"],
        "near": near,
        "ready": ready,
        "far": far,
        "near_ref": by_missing[1],
        "ready_ref": by_missing[0],
        "far_ref": by_missing[2],
        "course": course,
        "skill_c": c,
    }


def _training(stage: dict, ref: str) -> str:
    return f"/org/{stage['org']}/candidates/{stage['job']}/{ref}/training"


def _sponsor(stage: dict, ref: str) -> str:
    return f"/org/{stage['org']}/candidates/{stage['job']}/{ref}/sponsor"


async def _notices(client: AsyncClient, headers: dict[str, str]) -> list[dict]:
    everything = (await client.get("/me/notifications", headers=headers)).json()
    return [n for n in everything if n["template"] == "sponsor_offer"]


class TestSeeingTheTraining:
    async def test_it_names_the_one_missing_standard_and_the_course(
        self, client: AsyncClient, stage: dict
    ) -> None:
        response = await client.get(_training(stage, stage["near_ref"]), headers=stage["employer"])

        assert response.status_code == 200
        body = response.json()
        assert body["standard"]["nos_code"] == "HT/N0003"
        assert [c["slug"] for c in body["courses"]] == ["ht-course-c"]
        assert body["offered"] is False
        assert body["reference"] == stage["near_ref"]

    async def test_only_someone_exactly_one_standard_short_can_be_looked_up(
        self, client: AsyncClient, stage: dict
    ) -> None:
        """A reference is a handle, not a key: it resolves inside this vacancy's
        near-miss pool and nowhere else, so it cannot be used to probe for
        candidates who are ready, or too far away, or not there at all."""
        refused = [
            await client.get(_training(stage, stage["ready_ref"]), headers=stage["employer"]),
            await client.get(_training(stage, stage["far_ref"]), headers=stage["employer"]),
            await client.get(_training(stage, "C-DEADBEEF"), headers=stage["employer"]),
        ]
        assert [r.status_code for r in refused] == [404, 404, 404]
        # One answer for every reason, so the reason cannot be inferred.
        assert refused[0].json() == refused[1].json() == refused[2].json()

    async def test_another_organisation_cannot_use_this_vacancy(
        self, client: AsyncClient, stage: dict
    ) -> None:
        rival, _rival_org = await _employer(client, "Rival Co")
        # Their own prefix, our vacancy and reference: a 404, never data.
        response = await client.get(
            f"/org/{_rival_org}/candidates/{stage['job']}/{stage['near_ref']}/training",
            headers=rival,
        )
        assert response.status_code == 404

    async def test_signed_out_and_non_employers_are_refused(
        self, client: AsyncClient, stage: dict
    ) -> None:
        url = _training(stage, stage["near_ref"])
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=stage["near"])).status_code in (403, 404)


class TestOffering:
    async def test_the_candidate_gets_one_in_app_notice_naming_no_person(
        self, client: AsyncClient, stage: dict, db: AsyncSession
    ) -> None:
        response = await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])

        assert response.status_code == 201
        assert response.json() == {"offered": True}
        notices = await _notices(client, stage["near"])
        assert len(notices) == 1
        # The organisation, the standard, the course and a link to the vacancy.
        # Nothing about the candidate, and no score.
        assert set(notices[0]["payload"]) == {
            "vacancy",
            "organisation",
            "standard",
            "course",
            "path",
        }
        assert notices[0]["payload"]["organisation"] == "Train Co"
        assert notices[0]["payload"]["course"] == "Course C"
        assert notices[0]["payload"]["path"] == f"/jobs/{stage['job']}"

        rows = list(
            await db.scalars(select(Notification).where(Notification.template == "sponsor_offer"))
        )
        assert [r.channel for r in rows] == ["in_app"]

    async def test_nobody_else_is_told(self, client: AsyncClient, stage: dict) -> None:
        await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])

        assert await _notices(client, stage["ready"]) == []
        assert await _notices(client, stage["far"]) == []

    async def test_an_offer_is_made_once(self, client: AsyncClient, stage: dict) -> None:
        first = await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])
        again = await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])

        assert (first.status_code, again.status_code) == (201, 409)
        assert len(await _notices(client, stage["near"])) == 1
        looked = await client.get(_training(stage, stage["near_ref"]), headers=stage["employer"])
        assert looked.json()["offered"] is True

    async def test_a_candidate_outside_the_near_pool_cannot_be_offered(
        self, client: AsyncClient, stage: dict
    ) -> None:
        for ref in (stage["ready_ref"], stage["far_ref"], "C-DEADBEEF"):
            refused = await client.post(_sponsor(stage, ref), headers=stage["employer"])
            assert refused.status_code == 404
        assert await _notices(client, stage["ready"]) == []

    async def test_it_is_refused_when_no_course_teaches_the_standard(
        self, client: AsyncClient, stage: dict, db: AsyncSession
    ) -> None:
        """A promise to sponsor training that does not exist is one nobody can
        keep, and the notice would have nothing to name."""
        await db.execute(
            CourseSkill.__table__.delete().where(CourseSkill.skill_id == stage["skill_c"].id)
        )
        await db.commit()

        refused = await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])
        assert refused.status_code == 422
        assert await _notices(client, stage["near"]) == []

    async def test_a_closed_vacancy_cannot_be_used(
        self, client: AsyncClient, stage: dict, db: AsyncSession
    ) -> None:
        closed = await client.post(
            f"/org/{stage['org']}/jobs/{stage['job']}/close",
            headers=stage["employer"],
            json={"reason": "filled"},
        )
        assert closed.status_code == 200

        refused = await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])
        assert refused.status_code == 404


class TestTheCandidateIsProtected:
    async def _intent(self, db: AsyncSession, stage: dict) -> SponsorIntent | None:
        job = await db.scalar(select(Job).where(Job.slug == stage["job"]))
        assert job is not None
        return await db.scalar(select(SponsorIntent).where(SponsorIntent.job_id == job.id))

    async def test_an_opted_out_candidate_is_not_messaged_and_the_employer_cannot_tell(
        self, client: AsyncClient, stage: dict, db: AsyncSession
    ) -> None:
        # What they switched off is unsolicited mail, and this is unsolicited.
        await client.put("/me/profile", headers=stage["near"], json={"job_alerts_enabled": False})

        response = await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])

        # The same answer a notified candidate produces.
        assert response.status_code == 201
        assert response.json() == {"offered": True}
        assert await _notices(client, stage["near"]) == []
        # The offer is still the employer's fact; `notified_at` records that the
        # candidate was not told, and only the database knows.
        intent = await self._intent(db, stage)
        assert intent is not None and intent.notified_at is None

    async def test_an_offer_counts_against_the_daily_cap(
        self, client: AsyncClient, stage: dict, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import api.modules.alerts.sponsorship as sponsorship

        monkeypatch.setattr(
            sponsorship, "get_settings", lambda: SimpleNamespace(max_alerts_per_candidate_per_day=0)
        )
        response = await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])

        assert response.status_code == 201
        assert await _notices(client, stage["near"]) == []
        intent = await self._intent(db, stage)
        assert intent is not None and intent.notified_at is None

    async def test_the_employers_payloads_never_say_whether_the_candidate_was_told(
        self, client: AsyncClient, stage: dict
    ) -> None:
        await client.put("/me/profile", headers=stage["near"], json={"job_alerts_enabled": False})
        await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])

        body = (
            await client.get(_training(stage, stage["near_ref"]), headers=stage["employer"])
        ).json()
        assert set(body) == {"reference", "standard", "courses", "offered"}

    async def test_the_event_is_nameless(
        self, client: AsyncClient, stage: dict, db: AsyncSession
    ) -> None:
        await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])

        events = list(
            await db.scalars(
                select(AnalyticsEvent).where(AnalyticsEvent.name == "sponsor_intent_recorded")
            )
        )
        assert len(events) == 1
        assert events[0].subject_type == "job"
        assert events[0].payload == {"notified": True}


class TestErasure:
    async def test_erasing_the_candidate_takes_the_offer_with_it(
        self, client: AsyncClient, stage: dict, db: AsyncSession
    ) -> None:
        await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])
        assert await db.scalar(select(SponsorIntent.id)) is not None

        erased = await client.request(
            "DELETE", "/me/account", headers=stage["near"], json={"confirm": "DELETE"}
        )
        assert erased.status_code in (200, 204), erased.text
        db.expire_all()
        assert await db.scalar(select(SponsorIntent.id)) is None

    async def test_deleting_the_organisation_takes_its_offers_with_it(
        self, client: AsyncClient, stage: dict, db: AsyncSession
    ) -> None:
        from api.modules.privacy.service import _delete_tenant

        await client.post(_sponsor(stage, stage["near_ref"]), headers=stage["employer"])
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == stage["org"]))
        assert tenant is not None

        await _delete_tenant(db, tenant.id)
        await db.flush()
        assert await db.scalar(select(SponsorIntent.id)) is None
