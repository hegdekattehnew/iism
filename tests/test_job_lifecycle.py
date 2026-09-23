"""Sprint 27: a vacancy that ends, and alerts that reach people.

Two defects this closes, both of them things the product could compute and
would not act on:

* **"Hired" did nothing.** A vacancy stayed published after the last position
  was filled, kept ranking in strangers' matches, and kept taking applications
  nobody would read.
* **`match_jobs` ran only inside a request handler**, so a vacancy published on
  Monday reached a matched candidate only if they happened to open `/matches`.

The thing to watch here is **where a closed vacancy is still visible**. It is
not a draft: its page stays, its inbox stays, and the employer still works
through the people already in it. What stops is browse, matching, and new
applications -- and each of those is a separate query that had to be changed,
which is why `open_job()` exists and why this file checks all three.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.alerts.models import JobAlert
from api.modules.alerts.service import close_expired, sweep
from api.modules.analytics.models import AnalyticsEvent
from api.modules.identity import Tenant
from api.modules.marketplace.models import Job, JobSkill
from api.modules.notifications.models import Notification
from api.modules.skills import Skill


@pytest.fixture
async def world(db: AsyncSession) -> dict:
    """An employer, a two-position vacancy, and the standard it needs."""
    skill = Skill(
        slug="lifecycle-standard",
        name="Operate a till",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N8001",
        source="nsqf",
    )
    employer = Tenant(slug="lifecycle-co", name="Lifecycle Co", tenant_type="employer")
    db.add_all([skill, employer])
    await db.flush()

    job = Job(
        slug="two-cashiers",
        tenant_id=employer.id,
        title="Cashier",
        employment_type="full_time",
        status="published",
        positions=2,
        # Seeded as already-swept, like every row the migration backfilled, so
        # a test that does not care about alerts never accidentally sends any.
        alerted_at=datetime.now(UTC),
    )
    db.add(job)
    await db.flush()
    db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=5, is_mandatory=True))
    await db.commit()
    return {"db": db, "job": job, "skill": skill, "employer": employer}


async def _candidate(client: AsyncClient) -> dict[str, str]:
    phone = "9" + str(uuid.uuid4().int)[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _employer(client: AsyncClient, db: AsyncSession, job: Job) -> dict[str, str]:
    """An owner account attached to the fixture's existing tenant."""
    from api.modules.identity.models import Membership, User

    address = f"lifecycle-{uuid.uuid4().hex[:8]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "Throwaway",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    user = await db.scalar(select(User).where(User.email == address))
    db.add(Membership(user_id=user.id, tenant_id=job.tenant_id, role="owner"))
    await db.commit()
    return {"authorization": f"Bearer {tokens['access_token']}"}


async def _apply(client: AsyncClient, headers: dict[str, str], slug: str):  # type: ignore[no-untyped-def]
    return await client.post("/me/applications", headers=headers, json={"job_slug": slug})


# ------------------------------------------------------- closing and reopening


class TestClosing:
    async def test_closing_hides_it_from_browse_but_keeps_its_page(
        self, world: dict, client: AsyncClient
    ) -> None:
        """A closed vacancy is not a draft. People have its URL."""
        db, job = world["db"], world["job"]
        headers = await _employer(client, db, job)

        assert any(j["slug"] == "two-cashiers" for j in (await client.get("/jobs")).json()["items"])

        closed = await client.post(
            "/org/lifecycle-co/jobs/two-cashiers/close",
            headers=headers,
            json={"reason": "filled"},
        )
        assert closed.status_code == 200
        assert closed.json()["is_open"] is False
        assert closed.json()["close_reason"] == "filled"

        assert not any(
            j["slug"] == "two-cashiers" for j in (await client.get("/jobs")).json()["items"]
        )
        # The page survives: a 404 on a row we deliberately kept would be a
        # broken link of our own making.
        page = await client.get("/jobs/two-cashiers")
        assert page.status_code == 200
        assert page.json()["is_open"] is False

    async def test_a_closed_vacancy_refuses_new_applications_with_409_not_404(
        self, world: dict, client: AsyncClient
    ) -> None:
        """404 would be a lie the candidate can disprove by pressing Back."""
        db, job = world["db"], world["job"]
        employer = await _employer(client, db, job)
        await client.post(
            "/org/lifecycle-co/jobs/two-cashiers/close",
            headers=employer,
            json={"reason": "withdrawn"},
        )

        refused = await _apply(client, await _candidate(client), "two-cashiers")
        assert refused.status_code == 409
        assert "closed" in refused.json()["detail"].lower()

    async def test_the_applicants_still_waiting_are_told(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        db, job = world["db"], world["job"]
        seeker = await _candidate(client)
        assert (await _apply(client, seeker, "two-cashiers")).status_code == 201

        employer = await _employer(client, db, job)
        await client.post(
            "/org/lifecycle-co/jobs/two-cashiers/close",
            headers=employer,
            json={"reason": "withdrawn"},
        )

        notices = (
            await db.scalars(select(Notification).where(Notification.template == "vacancy_closed"))
        ).all()
        assert len(notices) == 1
        # The vacancy and a path; never the reason. "Filled" tells an applicant
        # somebody else got it, which is the employer's to say.
        assert "reason" not in notices[0].payload

    async def test_closing_twice_is_not_an_error(self, world: dict, client: AsyncClient) -> None:
        db, job = world["db"], world["job"]
        headers = await _employer(client, db, job)
        first = await client.post(
            "/org/lifecycle-co/jobs/two-cashiers/close", headers=headers, json={"reason": "filled"}
        )
        again = await client.post(
            "/org/lifecycle-co/jobs/two-cashiers/close", headers=headers, json={"reason": "filled"}
        )
        assert first.status_code == 200
        assert again.status_code == 200

    async def test_reopening_takes_applications_again(
        self, world: dict, client: AsyncClient
    ) -> None:
        db, job = world["db"], world["job"]
        headers = await _employer(client, db, job)
        await client.post(
            "/org/lifecycle-co/jobs/two-cashiers/close", headers=headers, json={"reason": "filled"}
        )
        reopened = await client.post("/org/lifecycle-co/jobs/two-cashiers/reopen", headers=headers)
        assert reopened.status_code == 200
        assert reopened.json()["is_open"] is True
        assert reopened.json()["close_reason"] is None
        assert (await _apply(client, await _candidate(client), "two-cashiers")).status_code == 201

    async def test_reopening_clears_a_closing_date_already_past(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Otherwise the worker closes it again within the hour and the
        employer sees their own action silently undone."""
        job = world["job"]
        headers = await _employer(client, db, job)
        job.closes_at = datetime.now(UTC) - timedelta(days=1)
        job.closed_at = datetime.now(UTC)
        job.close_reason = "expired"
        await db.commit()

        reopened = await client.post("/org/lifecycle-co/jobs/two-cashiers/reopen", headers=headers)
        assert reopened.status_code == 200
        assert reopened.json()["closes_at"] is None

    async def test_an_employer_cannot_claim_the_workers_reason(
        self, world: dict, client: AsyncClient
    ) -> None:
        """`expired` is written when a date passes. An employer claiming it
        would make the recorded reason a vacancy closed untrue."""
        db, job = world["db"], world["job"]
        headers = await _employer(client, db, job)
        refused = await client.post(
            "/org/lifecycle-co/jobs/two-cashiers/close",
            headers=headers,
            json={"reason": "expired"},
        )
        assert refused.status_code == 422

    async def test_closing_is_recorded(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        job = world["job"]
        headers = await _employer(client, db, job)
        await client.post(
            "/org/lifecycle-co/jobs/two-cashiers/close", headers=headers, json={"reason": "filled"}
        )
        rows = (
            await db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.name == "job_closed"))
        ).all()
        assert rows and rows[0].subject_type == "job"
        assert rows[0].payload["automatic"] is False


class TestHiredFinallyDoesSomething:
    async def test_the_vacancy_closes_when_the_last_position_is_filled(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """Two positions, two hires. The first must not close it."""
        job = world["job"]
        employer = await _employer(client, db, job)
        ids = []
        for _ in range(2):
            seeker = await _candidate(client)
            body = (await _apply(client, seeker, "two-cashiers")).json()
            ids.append(body["id"])

        first = await client.patch(
            f"/org/lifecycle-co/jobs/two-cashiers/applications/{ids[0]}",
            headers=employer,
            json={"status": "hired"},
        )
        assert first.status_code == 200
        await db.refresh(job)
        assert job.closed_at is None, "one hire against two positions must not close it"

        await client.patch(
            f"/org/lifecycle-co/jobs/two-cashiers/applications/{ids[1]}",
            headers=employer,
            json={"status": "hired"},
        )
        await db.refresh(job)
        assert job.closed_at is not None
        assert job.close_reason == "filled"

    async def test_the_automatic_close_is_recorded_as_automatic(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        job = world["job"]
        job.positions = 1
        await db.commit()
        employer = await _employer(client, db, job)
        seeker = await _candidate(client)
        body = (await _apply(client, seeker, "two-cashiers")).json()
        await client.patch(
            f"/org/lifecycle-co/jobs/two-cashiers/applications/{body['id']}",
            headers=employer,
            json={"status": "hired"},
        )
        rows = (
            await db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.name == "job_closed"))
        ).all()
        assert rows and rows[0].payload["automatic"] is True

    async def test_the_employer_can_still_work_through_the_inbox_after_it_closes(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """This is why closing is not unpublishing."""
        job = world["job"]
        job.positions = 1
        await db.commit()
        employer = await _employer(client, db, job)
        for _ in range(2):
            await _apply(client, await _candidate(client), "two-cashiers")
        listed = (
            await client.get("/org/lifecycle-co/jobs/two-cashiers/applications", headers=employer)
        ).json()
        body = listed["items"][0]
        await client.patch(
            f"/org/lifecycle-co/jobs/two-cashiers/applications/{body['application_id']}",
            headers=employer,
            json={"status": "hired"},
        )
        await db.refresh(job)
        assert job.closed_at is not None

        after = await client.get(
            "/org/lifecycle-co/jobs/two-cashiers/applications", headers=employer
        )
        assert after.status_code == 200
        assert after.json()["total"] == 2


class TestExpiry:
    async def test_the_worker_closes_a_vacancy_whose_date_has_passed(
        self, world: dict, db: AsyncSession
    ) -> None:
        """Enforced by the worker, never by a request: a date that only takes
        effect when somebody loads the page is not a closing date."""
        job = world["job"]
        job.closes_at = datetime.now(UTC) - timedelta(minutes=1)
        await db.commit()

        assert await close_expired(db) == 1
        await db.refresh(job)
        assert job.close_reason == "expired"

    async def test_a_future_date_is_left_alone(self, world: dict, db: AsyncSession) -> None:
        job = world["job"]
        job.closes_at = datetime.now(UTC) + timedelta(days=7)
        await db.commit()
        assert await close_expired(db) == 0
        await db.refresh(job)
        assert job.closed_at is None


# --------------------------------------------------------------- the invisible


class TestAClosedVacancyIsGoneFromEveryListing:
    """`open_job()` exists because fourteen queries compared
    `status == "published"`, and a closed vacancy would have stayed visible in
    whichever one was missed. These are the three that matter."""

    async def test_it_leaves_browse_the_count_and_matching(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, skill = world["job"], world["skill"]
        seeker = await _candidate(client)
        # Give the candidate the standard, so the vacancy genuinely matches.
        await client.post(
            "/me/profile/skills", headers=seeker, json={"skill_slug": skill.slug, "level": 4}
        )

        before_count = (await client.get("/marketplace/stats")).json()["jobs"]
        before_matches = (await client.get("/me/matches", headers=seeker)).json()
        assert any(m["job"]["slug"] == "two-cashiers" for m in before_matches["items"])

        job.closed_at = datetime.now(UTC)
        job.close_reason = "filled"
        await db.commit()

        after_count = (await client.get("/marketplace/stats")).json()["jobs"]
        after_matches = (await client.get("/me/matches", headers=seeker)).json()

        assert after_count == before_count - 1, "the homepage count must drop"
        assert not any(m["job"]["slug"] == "two-cashiers" for m in after_matches["items"])
        assert not any(
            j["slug"] == "two-cashiers" for j in (await client.get("/jobs")).json()["items"]
        )


# --------------------------------------------------------------------- alerts


class TestJobAlerts:
    async def test_a_matched_candidate_is_told_about_a_new_vacancy(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, skill = world["job"], world["skill"]
        seeker = await _candidate(client)
        await client.post(
            "/me/profile/skills", headers=seeker, json={"skill_slug": skill.slug, "level": 4}
        )
        # Unswept, as a freshly published vacancy is.
        job.alerted_at = None
        await db.commit()

        result = await sweep(db)
        assert result.jobs == 1
        assert result.alerts == 1

        notices = (
            await db.scalars(select(Notification).where(Notification.template == "job_alert"))
        ).all()
        # In-app always; email only where there is one, and a phone-only
        # candidate has none -- which is the honest reach of this feature.
        assert [n.channel for n in notices] == ["in_app"]
        assert "@" not in str(notices[0].payload)

    async def test_nobody_is_told_twice(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The unique constraint is what makes this impossible rather than
        unlikely; the `alerted_at` claim is what makes the sweep idempotent."""
        job, skill = world["job"], world["skill"]
        seeker = await _candidate(client)
        await client.post(
            "/me/profile/skills", headers=seeker, json={"skill_slug": skill.slug, "level": 4}
        )
        job.alerted_at = None
        await db.commit()

        assert (await sweep(db)).alerts == 1
        assert (await sweep(db)).alerts == 0, "a second sweep must find nothing"

        # And even if the job is re-offered, the row refuses a repeat.
        job.alerted_at = None
        await db.commit()
        assert (await sweep(db)).alerts == 0

    async def test_a_candidate_who_opted_out_hears_nothing(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, skill = world["job"], world["skill"]
        seeker = await _candidate(client)
        await client.post(
            "/me/profile/skills", headers=seeker, json={"skill_slug": skill.slug, "level": 4}
        )
        off = await client.put("/me/profile", headers=seeker, json={"job_alerts_enabled": False})
        assert off.status_code == 200
        assert off.json()["job_alerts_enabled"] is False

        job.alerted_at = None
        await db.commit()
        result = await sweep(db)
        assert result.alerts == 0
        assert result.skipped_opted_out == 1

    async def test_a_closed_vacancy_is_never_alerted(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, skill = world["job"], world["skill"]
        seeker = await _candidate(client)
        await client.post(
            "/me/profile/skills", headers=seeker, json={"skill_slug": skill.slug, "level": 4}
        )
        job.alerted_at = None
        job.closed_at = datetime.now(UTC)
        job.close_reason = "withdrawn"
        await db.commit()
        assert (await sweep(db)).jobs == 0

    async def test_a_candidate_with_nothing_in_common_is_not_told(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """One scorer (ADR-037). The sweep uses the employer console's pool,
        so 'close enough to write to' is the same question as 'close enough to
        rank' -- there is no second, looser rule."""
        job = world["job"]
        await _candidate(client)  # a profile with no skills at all
        job.alerted_at = None
        await db.commit()
        assert (await sweep(db)).alerts == 0

    async def test_the_daily_cap_holds(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A Monday of forty new listings must not be forty notifications."""
        from api.core.config import get_settings

        job, skill, employer = world["job"], world["skill"], world["employer"]
        seeker = await _candidate(client)
        await client.post(
            "/me/profile/skills", headers=seeker, json={"skill_slug": skill.slug, "level": 4}
        )
        limit = get_settings().max_alerts_per_candidate_per_day

        job.alerted_at = None
        for n in range(limit + 2):
            extra = Job(
                slug=f"extra-{n}",
                tenant_id=employer.id,
                title=f"Cashier {n}",
                employment_type="full_time",
                status="published",
            )
            db.add(extra)
            await db.flush()
            db.add(JobSkill(job_id=extra.id, skill_id=skill.id, importance=5, is_mandatory=True))
        await db.commit()

        total = 0
        for _ in range(4):
            total += (await sweep(db, limit=10)).alerts
        assert total == limit, f"expected exactly {limit} alerts, got {total}"

    async def test_erasure_takes_the_alert_history(
        self, world: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        job, skill = world["job"], world["skill"]
        seeker = await _candidate(client)
        await client.post(
            "/me/profile/skills", headers=seeker, json={"skill_slug": skill.slug, "level": 4}
        )
        job.alerted_at = None
        await db.commit()
        await sweep(db)
        assert (await db.scalar(select(func.count()).select_from(JobAlert))) == 1

        assert (await client.delete("/me/account", headers=seeker)).status_code == 204
        assert (await db.scalar(select(func.count()).select_from(JobAlert))) == 0
