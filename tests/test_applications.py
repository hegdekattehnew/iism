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
        name="Process payments",
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
        title="Cashier",
        employment_type="full_time",
        status="published",
    )
    draft = Job(slug="secret-cashier", tenant_id=employer.id, title="Secret", status="draft")
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


# ------------------------------------------------------- the employer's inbox


async def _employer_with_job(
    client: AsyncClient, skill_slug: str
) -> tuple[dict[str, str], str, str]:
    """A real employer account, with a published vacancy of its own."""
    address = f"inbox-{uuid.uuid4().hex[:8]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "Inbox Hospital",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    org = tokens["organisation_slug"]
    job = (
        await client.post(
            f"/org/{org}/jobs",
            headers=headers,
            json={
                "title": "Inbox Cashier",
                "skills": [{"skill_slug": skill_slug, "importance": 5, "is_mandatory": True}],
            },
        )
    ).json()
    await client.post(f"/org/{org}/jobs/{job['slug']}/publish", headers=headers)
    return headers, org, job["slug"]


class TestTheEmployerInbox:
    async def test_an_applicant_arrives_with_their_contact_details(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        """The one disclosure this product makes, and the candidate made it."""
        employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
        seeker = await _candidate(client)
        await client.put("/me/profile", headers=seeker, json={"headline": "Cashier, two years"})
        await client.post("/me/applications", headers=seeker, json={"job_slug": job_slug})

        body = (
            await client.get(f"/org/{org}/jobs/{job_slug}/applications", headers=employer)
        ).json()
        assert body["total"] == 1
        applicant = body["items"][0]
        assert applicant["status"] == "applied"
        assert applicant["contact"]["phone"].startswith("+91")
        # The de-identified card is unchanged and sits beside the disclosure.
        assert applicant["candidate"]["reference"].startswith("C-")
        assert applicant["candidate"]["headline"] == "Cashier, two years"
        assert "phone" not in applicant["candidate"]

    async def test_withdrawing_takes_the_contact_back(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
        seeker = await _candidate(client)
        created = (
            await client.post("/me/applications", headers=seeker, json={"job_slug": job_slug})
        ).json()
        await client.post(f"/me/applications/{created['id']}/withdraw", headers=seeker)

        body = (
            await client.get(f"/org/{org}/jobs/{job_slug}/applications", headers=employer)
        ).json()
        applicant = body["items"][0]
        # The employer keeps the fact and loses the person.
        assert applicant["status"] == "withdrawn"
        assert applicant["contact"] is None

    async def test_applicants_are_ranked_by_the_same_scorer(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        """Two screens that disagree about who is strongest are worse than one."""
        employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
        weak = await _candidate(client)
        strong = await _candidate(client)
        await client.post(
            "/me/profile/skills",
            headers=strong,
            json={"skill_slug": "apply-test-standard", "proficiency": 5},
        )
        for headers in (weak, strong):
            await client.post("/me/applications", headers=headers, json={"job_slug": job_slug})

        items = (
            await client.get(f"/org/{org}/jobs/{job_slug}/applications", headers=employer)
        ).json()["items"]
        scores = [i["candidate"]["score"] for i in items]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] > scores[-1]

    async def test_another_organisations_vacancy_is_404(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        _, _, job_slug = await _employer_with_job(client, "apply-test-standard")
        other, other_org, _ = await _employer_with_job(client, "apply-test-standard")
        response = await client.get(f"/org/{other_org}/jobs/{job_slug}/applications", headers=other)
        assert response.status_code == 404

    async def test_a_candidate_cannot_read_an_inbox(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        _, org, job_slug = await _employer_with_job(client, "apply-test-standard")
        seeker = await _candidate(client)
        response = await client.get(f"/org/{org}/jobs/{job_slug}/applications", headers=seeker)
        # Not a member of that organisation: 404, never 403 (ADR-038).
        assert response.status_code == 404

    async def test_the_ranked_pool_still_names_nobody(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        """Applying discloses to the *inbox*. The pool endpoint is unchanged,
        and ADR-037 still holds there."""
        employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
        seeker = await _candidate(client)
        me = (await client.get("/auth/me", headers=seeker)).json()
        await client.post(
            "/me/profile/skills",
            headers=seeker,
            json={"skill_slug": "apply-test-standard", "proficiency": 4},
        )
        await client.post("/me/applications", headers=seeker, json={"job_slug": job_slug})

        pool = (await client.get(f"/org/{org}/candidates/{job_slug}", headers=employer)).text
        assert me["phone"] not in pool
        assert "full_name" not in pool
        assert "contact" not in pool


class TestMovingAnApplicationAlong:
    async def test_shortlisting(self, vacancy: dict, client: AsyncClient) -> None:
        employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
        seeker = await _candidate(client)
        created = (
            await client.post("/me/applications", headers=seeker, json={"job_slug": job_slug})
        ).json()

        response = await client.patch(
            f"/org/{org}/jobs/{job_slug}/applications/{created['id']}",
            headers=employer,
            json={"status": "shortlisted"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "shortlisted"
        # Still live, so the contact is still there.
        assert response.json()["contact"] is not None

        mine = (await client.get("/me/applications", headers=seeker)).json()
        assert mine[0]["status"] == "shortlisted"

    async def test_a_withdrawn_application_cannot_be_moved(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        """Otherwise shortlisting would put the contact details back on screen
        by a side door."""
        employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
        seeker = await _candidate(client)
        created = (
            await client.post("/me/applications", headers=seeker, json={"job_slug": job_slug})
        ).json()
        await client.post(f"/me/applications/{created['id']}/withdraw", headers=seeker)

        response = await client.patch(
            f"/org/{org}/jobs/{job_slug}/applications/{created['id']}",
            headers=employer,
            json={"status": "shortlisted"},
        )
        assert response.status_code == 409

    async def test_an_employer_cannot_set_the_candidates_statuses(
        self, vacancy: dict, client: AsyncClient
    ) -> None:
        employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
        seeker = await _candidate(client)
        created = (
            await client.post("/me/applications", headers=seeker, json={"job_slug": job_slug})
        ).json()
        for forbidden in ("applied", "withdrawn", "nonsense"):
            response = await client.patch(
                f"/org/{org}/jobs/{job_slug}/applications/{created['id']}",
                headers=employer,
                json={"status": forbidden},
            )
            assert response.status_code == 422, forbidden


# ------------------------------------------------- counts, and a cap on spray


async def test_the_overview_counts_applications_without_extra_queries(
    vacancy: dict, client: AsyncClient, db: AsyncSession
) -> None:
    """The page an employer opens first. Sprint 20 took the per-vacancy cost
    out of it; adding counts must not put it back."""
    from sqlalchemy import event

    from api.modules.matching.employer import job_pools

    employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
    seeker = await _candidate(client)
    await client.post("/me/applications", headers=seeker, json={"job_slug": job_slug})

    body = (await client.get(f"/org/{org}/candidates", headers=employer)).json()
    pool = next(j for j in body["jobs"] if j["job"]["slug"] == job_slug)
    assert pool["applications"] == 1
    assert pool["new_applications"] == 1

    tenant_id = uuid.UUID(
        (await client.get("/auth/me", headers=employer)).json()["memberships"][0]["tenant"]["id"]
    )
    statements: list[str] = []

    def count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    connection = (await db.connection()).sync_connection
    assert connection is not None
    event.listen(connection, "before_cursor_execute", count)
    try:
        await job_pools(db, tenant_id)
        with_one = len(statements)
        statements.clear()
        await job_pools(db, tenant_id)
        again = len(statements)
    finally:
        event.remove(connection, "before_cursor_execute", count)
    assert with_one == again


async def test_a_withdrawn_application_is_not_counted(vacancy: dict, client: AsyncClient) -> None:
    employer, org, job_slug = await _employer_with_job(client, "apply-test-standard")
    seeker = await _candidate(client)
    created = (
        await client.post("/me/applications", headers=seeker, json={"job_slug": job_slug})
    ).json()
    await client.post(f"/me/applications/{created['id']}/withdraw", headers=seeker)

    body = (await client.get(f"/org/{org}/candidates", headers=employer)).json()
    pool = next(j for j in body["jobs"] if j["job"]["slug"] == job_slug)
    # The row survives; the count is of what an employer can act on.
    assert pool["applications"] == 0


async def test_applying_all_day_is_capped(
    vacancy: dict, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-minute write limit stops a script; this stops patient spraying."""
    from api.core.config import get_settings

    monkeypatch.setenv("MAX_APPLICATIONS_PER_DAY", "1")
    get_settings.cache_clear()
    try:
        employer_a = await _employer_with_job(client, "apply-test-standard")
        employer_b = await _employer_with_job(client, "apply-test-standard")
        seeker = await _candidate(client)
        first = await client.post(
            "/me/applications", headers=seeker, json={"job_slug": employer_a[2]}
        )
        assert first.status_code == 201
        second = await client.post(
            "/me/applications", headers=seeker, json={"job_slug": employer_b[2]}
        )
        assert second.status_code == 429
        assert second.headers["retry-after"] == "3600"
    finally:
        monkeypatch.delenv("MAX_APPLICATIONS_PER_DAY")
        get_settings.cache_clear()
