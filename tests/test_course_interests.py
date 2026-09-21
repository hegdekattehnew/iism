"""Sprint 24: the course loop closes.

Twenty-three sprints told a learner which courses close their gap and gave them
nothing to press, and told the provider who published those courses nothing at
all. These cover both halves: registering interest, withdrawing, and what a
provider may see as a result.

The disclosure is the thing to watch. Registering interest is the **second**
act in this product that moves a name across a line -- here to a training
provider -- and withdrawing takes it back.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import Tenant
from api.modules.interests import CourseInterest
from api.modules.marketplace.models import Course, CourseSkill
from api.modules.notifications.models import Notification
from api.modules.skills import Skill


@pytest.fixture
async def catalogue(db: AsyncSession) -> dict:
    """One published course, one draft, and a second provider's course."""
    skill = Skill(
        slug="interest-test-standard",
        name="Collect blood samples",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N8001",
        source="nsqf",
    )
    provider = Tenant(slug="learn-co", name="Learn Co", tenant_type="course_provider")
    rival = Tenant(slug="rival-academy", name="Rival Academy", tenant_type="course_provider")
    db.add_all([skill, provider, rival])
    await db.flush()

    published = Course(
        slug="open-phlebotomy",
        tenant_id=provider.id,
        title="Phlebotomy Refresher",
        mode="offline",
        status="published",
    )
    draft = Course(slug="secret-course", tenant_id=provider.id, title="Secret", status="draft")
    theirs = Course(
        slug="rival-course",
        tenant_id=rival.id,
        title="Rival Course",
        mode="online",
        status="published",
    )
    db.add_all([published, draft, theirs])
    await db.flush()
    db.add(CourseSkill(course_id=published.id, skill_id=skill.id, level_taught=4))
    await db.commit()
    return {"course": published, "draft": draft, "rival_course": theirs, "provider": provider}


async def _candidate(client: AsyncClient) -> dict[str, str]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _organisation(client: AsyncClient, tenant_type: str, name: str) -> dict[str, str]:
    address = f"int-{uuid.uuid4().hex[:8]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": name,
                "tenant_type": tenant_type,
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    return {
        "authorization": f"Bearer {tokens['access_token']}",
        "slug": tokens["organisation_slug"],
    }


async def _owner_of(client: AsyncClient, db: AsyncSession, tenant: Tenant) -> dict[str, str]:
    """An owner account for a tenant the fixture created directly.

    Registration makes its own tenant, so the membership is moved onto the one
    under test -- the seed does the same thing for the same reason.
    """
    from api.modules.identity.models import Membership

    org = await _organisation(client, "course_provider", "Temp Provider")
    membership = await db.scalar(
        select(Membership)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(Tenant.slug == org["slug"])
    )
    membership.tenant_id = tenant.id
    await db.commit()
    return {"authorization": org["authorization"]}


# ------------------------------------------------------- registering interest


class TestRegisteringInterest:
    async def test_it_records_the_disclosure(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _candidate(client)
        response = await client.post(
            "/me/course-interests",
            headers=headers,
            json={"course_slug": "open-phlebotomy", "message": "Evenings only please."},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["course"]["slug"] == "open-phlebotomy"
        assert body["status"] == "registered"

        row = await db.scalar(select(CourseInterest).where(CourseInterest.id == body["id"]))
        assert row.contact_shared_at is not None
        assert row.contact_revoked_at is None

    async def test_registering_twice_is_refused(self, catalogue: dict, client: AsyncClient) -> None:
        headers = await _candidate(client)
        await client.post(
            "/me/course-interests", headers=headers, json={"course_slug": "open-phlebotomy"}
        )
        again = await client.post(
            "/me/course-interests", headers=headers, json={"course_slug": "open-phlebotomy"}
        )
        assert again.status_code == 409

    async def test_registering_after_withdrawing_reuses_the_row(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Somebody who changes their mind should not be told they already did
        something they took back."""
        headers = await _candidate(client)
        first = (
            await client.post(
                "/me/course-interests", headers=headers, json={"course_slug": "open-phlebotomy"}
            )
        ).json()
        await client.post(f"/me/course-interests/{first['id']}/withdraw", headers=headers)
        again = await client.post(
            "/me/course-interests", headers=headers, json={"course_slug": "open-phlebotomy"}
        )

        assert again.status_code == 201
        assert again.json()["id"] == first["id"]
        held = await db.scalar(select(func.count()).select_from(CourseInterest))
        assert held == 1
        row = await db.scalar(select(CourseInterest).where(CourseInterest.id == first["id"]))
        assert row.contact_revoked_at is None

    async def test_a_draft_course_cannot_be_registered_for(
        self, catalogue: dict, client: AsyncClient
    ) -> None:
        headers = await _candidate(client)
        response = await client.post(
            "/me/course-interests", headers=headers, json={"course_slug": "secret-course"}
        )
        assert response.status_code == 404

    async def test_an_unknown_course_is_404(self, catalogue: dict, client: AsyncClient) -> None:
        headers = await _candidate(client)
        response = await client.post(
            "/me/course-interests", headers=headers, json={"course_slug": "no-such-course"}
        )
        assert response.status_code == 404

    async def test_an_organisation_only_account_is_refused(
        self, catalogue: dict, client: AsyncClient
    ) -> None:
        """`get_current_candidate`, so pressing the button can never create a
        candidate profile for an account that never asked for one."""
        org = await _organisation(client, "employer", "No Seeker Co")
        response = await client.post(
            "/me/course-interests",
            headers={"authorization": org["authorization"]},
            json={"course_slug": "open-phlebotomy"},
        )
        assert response.status_code == 403

    async def test_the_daily_cap_refuses_a_sprayer(
        self, catalogue: dict, client: AsyncClient, monkeypatch
    ) -> None:
        from api.core.config import get_settings

        monkeypatch.setenv("MAX_COURSE_INTERESTS_PER_DAY", "1")
        get_settings.cache_clear()
        try:
            headers = await _candidate(client)
            await client.post(
                "/me/course-interests", headers=headers, json={"course_slug": "open-phlebotomy"}
            )
            second = await client.post(
                "/me/course-interests", headers=headers, json={"course_slug": "rival-course"}
            )
            assert second.status_code == 429
            assert second.headers["retry-after"]
        finally:
            monkeypatch.delenv("MAX_COURSE_INTERESTS_PER_DAY")
            get_settings.cache_clear()


class TestWithdrawing:
    async def test_it_keeps_the_row_and_takes_the_contact_back(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _candidate(client)
        created = (
            await client.post(
                "/me/course-interests", headers=headers, json={"course_slug": "open-phlebotomy"}
            )
        ).json()
        response = await client.post(
            f"/me/course-interests/{created['id']}/withdraw", headers=headers
        )

        assert response.status_code == 200
        assert response.json()["status"] == "withdrawn"
        row = await db.scalar(select(CourseInterest).where(CourseInterest.id == created["id"]))
        assert row is not None, "the row stays; only the disclosure goes"
        assert row.contact_revoked_at is not None

    async def test_somebody_elses_interest_is_a_404_not_a_403(
        self, catalogue: dict, client: AsyncClient
    ) -> None:
        mine = await _candidate(client)
        created = (
            await client.post(
                "/me/course-interests", headers=mine, json={"course_slug": "open-phlebotomy"}
            )
        ).json()
        theirs = await _candidate(client)
        response = await client.post(
            f"/me/course-interests/{created['id']}/withdraw", headers=theirs
        )
        assert response.status_code == 404


# --------------------------------------------------------- the provider's side


class TestWhatAProviderSees:
    async def test_a_live_interest_names_the_learner(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        learner = await _candidate(client)
        await client.put("/me/profile", headers=learner, json={"full_name": "Priya Sharma"})
        await client.post(
            "/me/course-interests",
            headers=learner,
            json={"course_slug": "open-phlebotomy", "message": "Evenings only"},
        )
        provider = await _owner_of(client, db, catalogue["provider"])

        body = (
            await client.get("/org/learn-co/courses/open-phlebotomy/interests", headers=provider)
        ).json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["contact"]["full_name"] == "Priya Sharma"
        assert item["contact"]["phone"]
        assert item["message"] == "Evenings only"

    async def test_a_withdrawn_interest_names_nobody(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        learner = await _candidate(client)
        created = (
            await client.post(
                "/me/course-interests",
                headers=learner,
                json={"course_slug": "open-phlebotomy", "message": "Evenings only"},
            )
        ).json()
        await client.post(f"/me/course-interests/{created['id']}/withdraw", headers=learner)
        provider = await _owner_of(client, db, catalogue["provider"])

        item = (
            await client.get("/org/learn-co/courses/open-phlebotomy/interests", headers=provider)
        ).json()["items"][0]
        assert item["status"] == "withdrawn"
        assert item["contact"] is None
        # Not even their note or their district: the provider keeps the fact
        # and loses the person entirely.
        assert item["message"] is None
        assert item["location_state"] is None

    async def test_the_payload_never_scores_a_learner(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A course publishes what it teaches, not what it requires, so there
        is nothing to rank against -- and inventing something would be the
        second scorer ADR-037 forbids."""
        learner = await _candidate(client)
        await client.post(
            "/me/course-interests", headers=learner, json={"course_slug": "open-phlebotomy"}
        )
        provider = await _owner_of(client, db, catalogue["provider"])
        item = (
            await client.get("/org/learn-co/courses/open-phlebotomy/interests", headers=provider)
        ).json()["items"][0]

        for absent in ("score", "coverage", "matched", "missing", "candidate", "user_id"):
            assert absent not in item, f"{absent} must not reach a provider"

    async def test_an_employer_is_refused_the_learner_list(
        self, catalogue: dict, client: AsyncClient
    ) -> None:
        """The mirror of a provider being refused the candidate pool."""
        employer = await _organisation(client, "employer", "Hiring Co")
        response = await client.get(
            f"/org/{employer['slug']}/interests",
            headers={"authorization": employer["authorization"]},
        )
        assert response.status_code == 403

    async def test_another_providers_course_is_a_404(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        provider = await _owner_of(client, db, catalogue["provider"])
        response = await client.get(
            "/org/learn-co/courses/rival-course/interests", headers=provider
        )
        assert response.status_code == 404

    async def test_a_non_member_gets_404_never_403(
        self, catalogue: dict, client: AsyncClient
    ) -> None:
        stranger = await _organisation(client, "course_provider", "Stranger Academy")
        response = await client.get(
            "/org/learn-co/courses/open-phlebotomy/interests",
            headers={"authorization": stranger["authorization"]},
        )
        assert response.status_code == 404

    async def test_marking_contacted_keeps_the_contact(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        learner = await _candidate(client)
        await client.post(
            "/me/course-interests", headers=learner, json={"course_slug": "open-phlebotomy"}
        )
        provider = await _owner_of(client, db, catalogue["provider"])
        listed = (
            await client.get("/org/learn-co/courses/open-phlebotomy/interests", headers=provider)
        ).json()["items"][0]

        response = await client.patch(
            f"/org/learn-co/courses/open-phlebotomy/interests/{listed['interest_id']}",
            headers=provider,
            json={"status": "contacted"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "contacted"
        assert response.json()["contact"] is not None

    async def test_a_withdrawn_interest_cannot_be_moved_along(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Otherwise marking it contacted would put the contact back on screen
        by a side door."""
        learner = await _candidate(client)
        created = (
            await client.post(
                "/me/course-interests", headers=learner, json={"course_slug": "open-phlebotomy"}
            )
        ).json()
        provider = await _owner_of(client, db, catalogue["provider"])
        listed = (
            await client.get("/org/learn-co/courses/open-phlebotomy/interests", headers=provider)
        ).json()["items"][0]
        await client.post(f"/me/course-interests/{created['id']}/withdraw", headers=learner)

        response = await client.patch(
            f"/org/learn-co/courses/open-phlebotomy/interests/{listed['interest_id']}",
            headers=provider,
            json={"status": "contacted"},
        )
        assert response.status_code == 409

    async def test_the_roll_up_counts_live_and_total(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        one = await _candidate(client)
        two = await _candidate(client)
        created = (
            await client.post(
                "/me/course-interests", headers=one, json={"course_slug": "open-phlebotomy"}
            )
        ).json()
        await client.post(
            "/me/course-interests", headers=two, json={"course_slug": "open-phlebotomy"}
        )
        await client.post(f"/me/course-interests/{created['id']}/withdraw", headers=one)

        provider = await _owner_of(client, db, catalogue["provider"])
        rows = (await client.get("/org/learn-co/interests", headers=provider)).json()
        ours = next(r for r in rows if r["course_slug"] == "open-phlebotomy")
        assert (ours["live"], ours["total"]) == (1, 2)
        # Every course of theirs appears, including the ones nobody wants yet.
        assert {r["course_slug"] for r in rows} == {"open-phlebotomy", "secret-course"}


# ------------------------------------------------------- told, and measured


class TestTheProviderIsTold:
    async def test_a_notification_is_queued_to_the_organisation(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        learner = await _candidate(client)
        await client.post(
            "/me/course-interests", headers=learner, json={"course_slug": "open-phlebotomy"}
        )
        queued = await db.scalar(
            select(Notification).where(
                Notification.template == "course_interest_registered",
                Notification.recipient_id == catalogue["provider"].id,
            )
        )
        assert queued is not None
        assert queued.recipient_kind == "tenant"
        # The course and a path, and nothing about the learner.
        assert queued.payload["course"] == "Phlebotomy Refresher"
        assert "learner" not in str(queued.payload).lower()

    async def test_registering_and_withdrawing_are_measured(
        self, catalogue: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`record()` swallows its own failures, so a forgotten CHECK migration
        shows up only as events that silently never appear -- which is what
        this test is really for."""
        learner = await _candidate(client)
        created = (
            await client.post(
                "/me/course-interests", headers=learner, json={"course_slug": "open-phlebotomy"}
            )
        ).json()
        await client.post(f"/me/course-interests/{created['id']}/withdraw", headers=learner)

        names = set(
            (
                await db.scalars(
                    select(AnalyticsEvent.name).where(
                        AnalyticsEvent.subject_id == catalogue["course"].id
                    )
                )
            ).all()
        )
        assert {"course_interest_registered", "course_interest_withdrawn"} <= names
