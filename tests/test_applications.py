"""Sprint 21: the loop closes.

For twenty sprints the product could compute an outcome and not produce one --
a candidate saw ranked vacancies with no button, an employer saw a pool it
could not reach. These tests cover the candidate's half: applying, withdrawing,
and saving a vacancy for later.

The disclosure is the thing to watch. Applying is the **only** act in this
product that moves a name across the line to an employer, and withdrawing takes
it back; `contact_shared_at` and `contact_revoked_at` are the record of both.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics.models import AnalyticsEvent
from api.modules.applications import Application, SavedJob
from api.modules.identity import Tenant
from api.modules.marketplace.models import Job, JobSkill
from api.modules.skills import Skill


@pytest.fixture
async def vacancy(db: AsyncSession) -> dict:
    """One published vacancy, one draft, and the standard they need."""
    skill = Skill(
        slug="apply-test-standard",
        name_en="Process payments",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N7001",
        source="nsqf",
    )
    employer = Tenant(slug="apply-co", name="Apply Co", tenant_type="employer")
    db.add_all([skill, employer])
    await db.flush()

    published = Job(
        slug="open-cashier",
        tenant_id=employer.id,
        title_en="Cashier",
        employment_type="full_time",
        status="published",
    )
    draft = Job(slug="secret-cashier", tenant_id=employer.id, title_en="Secret", status="draft")
    db.add_all([published, draft])
    await db.flush()
    db.add(JobSkill(job_id=published.id, skill_id=skill.id, importance=5, is_mandatory=True))
    await db.commit()
    return {"db": db, "job": published, "draft": draft, "skill": skill, "employer": employer}


async def _candidate(client: AsyncClient) -> dict[str, str]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _organisation(client: AsyncClient) -> dict[str, str]:
    address = f"apply-{uuid.uuid4().hex[:8]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "No Seeker Co",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    return {"authorization": f"Bearer {tokens['access_token']}"}


# ------------------------------------------------------------------- applying


class TestApplying:
    async def test_applying_creates_one_and_records_the_disclosure(
        self, vacancy: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _candidate(client)
        response = await client.post(
            "/me/applications",
            headers=headers,
            json={"job_slug": "open-cashier", "message": "I have done this work."},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "applied"
        assert body["job"]["slug"] == "open-cashier"
        assert body["job"]["tenant"]["name"] == "Apply Co"

        row = await db.scalar(select(Application).where(Application.id == uuid.UUID(body["id"])))
        assert row is not None
        # The consent record for the one disclosure this product makes.
        assert row.contact_shared_at is not None
        assert row.contact_revoked_at is None

    async def test_applying_twice_is_refused(self, vacancy: dict, client: AsyncClient) -> None:
        headers = await _candidate(client)
        first = await client.post(
            "/me/applications", headers=headers, json={"job_slug": "open-cashier"}
        )
        assert first.status_code == 201
        second = await client.post(
            "/me/applications", headers=headers, json={"job_slug": "open-cashier"}
        )
        assert second.status_code == 409

    async def test_a_draft_vacancy_cannot_be_applied_to(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        """Same rule as public browse: a listing nobody may read is not one
        anybody may apply to."""
        headers = await _candidate(client)
        response = await client.post(
            "/me/applications", headers=headers, json={"job_slug": "secret-cashier"}
        )
        assert response.status_code == 404

    async def test_an_unknown_vacancy_is_404(self, vacancy: dict, client: AsyncClient) -> None:
        headers = await _candidate(client)
        assert (
            await client.post("/me/applications", headers=headers, json={"job_slug": "nope"})
        ).status_code == 404

    async def test_a_candidate_with_no_skills_may_still_apply(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        """Profile completeness is the candidate's business. A marketplace that
        refuses the under-qualified is making a hiring decision on an
        employer's behalf."""
        headers = await _candidate(client)
        assert (
            await client.post(
                "/me/applications", headers=headers, json={"job_slug": "open-cashier"}
            )
        ).status_code == 201

    async def test_an_organisation_only_account_cannot_apply(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        """`get_current_candidate`, not `get_current_user`: pressing Apply must
        not create a candidate profile for an account that never asked for one."""
        headers = await _organisation(client)
        response = await client.post(
            "/me/applications", headers=headers, json={"job_slug": "open-cashier"}
        )
        assert response.status_code == 403

    async def test_applying_needs_a_signed_in_caller(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        assert (
            await client.post("/me/applications", json={"job_slug": "open-cashier"})
        ).status_code == 401

    async def test_the_covering_note_is_bounded(self, vacancy: dict, client: AsyncClient) -> None:
        headers = await _candidate(client)
        response = await client.post(
            "/me/applications",
            headers=headers,
            json={"job_slug": "open-cashier", "message": "x" * 1_001},
        )
        assert response.status_code == 422

    async def test_the_event_reaches_the_database(
        self, vacancy: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """`record()` swallows its own failures, so a name missing from the
        CHECK would leave no trace but an absent row. This is what catches it."""
        headers = await _candidate(client)
        await client.post("/me/applications", headers=headers, json={"job_slug": "open-cashier"})
        count = await db.scalar(
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(AnalyticsEvent.name == "application_submitted")
        )
        assert count == 1


# ---------------------------------------------------------------- withdrawing


class TestWithdrawing:
    async def test_withdrawing_revokes_the_contact(
        self, vacancy: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _candidate(client)
        created = (
            await client.post(
                "/me/applications", headers=headers, json={"job_slug": "open-cashier"}
            )
        ).json()

        response = await client.post(f"/me/applications/{created['id']}/withdraw", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "withdrawn"

        db.expire_all()
        row = await db.scalar(select(Application).where(Application.id == uuid.UUID(created["id"])))
        assert row is not None
        # The row stays -- the employer keeps the fact -- and the disclosure ends.
        assert row.contact_revoked_at is not None
        assert row.contact_is_visible is False

    async def test_withdrawing_twice_is_not_an_error(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        headers = await _candidate(client)
        created = (
            await client.post(
                "/me/applications", headers=headers, json={"job_slug": "open-cashier"}
            )
        ).json()
        for _ in range(2):
            response = await client.post(
                f"/me/applications/{created['id']}/withdraw", headers=headers
            )
            assert response.status_code == 200

    async def test_reapplying_after_withdrawal_reuses_the_row(
        self, vacancy: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """One application per candidate per vacancy, and someone who changed
        their mind is not told they have already applied to something they
        took back."""
        headers = await _candidate(client)
        created = (
            await client.post(
                "/me/applications", headers=headers, json={"job_slug": "open-cashier"}
            )
        ).json()
        await client.post(f"/me/applications/{created['id']}/withdraw", headers=headers)

        again = await client.post(
            "/me/applications", headers=headers, json={"job_slug": "open-cashier"}
        )
        assert again.status_code == 201
        assert again.json()["id"] == created["id"]
        assert again.json()["status"] == "applied"

        db.expire_all()
        count = await db.scalar(select(func.count()).select_from(Application))
        assert count == 1

    async def test_someone_elses_application_is_404(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        mine = await _candidate(client)
        theirs = await _candidate(client)
        created = (
            await client.post("/me/applications", headers=theirs, json={"job_slug": "open-cashier"})
        ).json()
        response = await client.post(f"/me/applications/{created['id']}/withdraw", headers=mine)
        assert response.status_code == 404


# ----------------------------------------------------------------- my listing


async def test_my_applications_lists_newest_first(vacancy: dict, client: AsyncClient) -> None:
    headers = await _candidate(client)
    await client.post("/me/applications", headers=headers, json={"job_slug": "open-cashier"})
    body = (await client.get("/me/applications", headers=headers)).json()
    assert [a["job"]["slug"] for a in body] == ["open-cashier"]
    assert body[0]["status"] == "applied"


async def test_my_applications_shows_nobody_elses(vacancy: dict, client: AsyncClient) -> None:
    mine = await _candidate(client)
    theirs = await _candidate(client)
    await client.post("/me/applications", headers=theirs, json={"job_slug": "open-cashier"})
    assert (await client.get("/me/applications", headers=mine)).json() == []


# --------------------------------------------------------------- saved jobs


class TestSavedJobs:
    async def test_saving_is_idempotent_and_private(
        self, vacancy: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _candidate(client)
        for _ in range(2):
            response = await client.post(
                "/me/saved-jobs", headers=headers, json={"job_slug": "open-cashier"}
            )
            assert response.status_code == 201

        db.expire_all()
        assert await db.scalar(select(func.count()).select_from(SavedJob)) == 1
        # Saving shares nothing: no application exists, so no contact was
        # disclosed to anyone.
        assert await db.scalar(select(func.count()).select_from(Application)) == 0

    async def test_listing_and_unsaving(self, vacancy: dict, client: AsyncClient) -> None:
        headers = await _candidate(client)
        await client.post("/me/saved-jobs", headers=headers, json={"job_slug": "open-cashier"})
        assert [
            s["job"]["slug"] for s in (await client.get("/me/saved-jobs", headers=headers)).json()
        ] == ["open-cashier"]

        assert (
            await client.delete("/me/saved-jobs/open-cashier", headers=headers)
        ).status_code == 204
        assert (await client.get("/me/saved-jobs", headers=headers)).json() == []

    async def test_unsaving_something_never_saved_is_not_an_error(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        headers = await _candidate(client)
        assert (
            await client.delete("/me/saved-jobs/open-cashier", headers=headers)
        ).status_code == 204
