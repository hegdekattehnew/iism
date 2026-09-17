"""Sprint 22: the loop stops being silent.

Sprint 21 let a candidate apply and an employer see them, and told nobody.
These cover the queue that fixes it, and the two properties that matter more
than the words: **delivery can never fail the thing it describes**, and the row
never holds an address.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.notifications import Notification, drain
from api.modules.notifications.templates import render


async def _employer_with_job(
    client: AsyncClient, skill_slug: str
) -> tuple[dict[str, str], str, str]:
    address = f"notify-{uuid.uuid4().hex[:8]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "Notified Clinic",
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
                "title_": "Ward Assistant",
                "skills": [{"skill_slug": skill_slug, "importance": 5, "is_mandatory": True}],
            },
        )
    ).json()
    return headers, org, job["slug"]


@pytest.fixture
async def stage(db: AsyncSession, client: AsyncClient) -> dict:
    """A published vacancy, an employer who can be told about it, and a candidate."""
    from decimal import Decimal

    from api.modules.skills import Skill

    skill = Skill(
        slug="notify-standard",
        name="Handle admissions",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N8001",
        source="nsqf",
    )
    db.add(skill)
    await db.commit()

    address = f"notify-{uuid.uuid4().hex[:8]}@example.org"
    code = (
        await client.post(
            "/auth/org/register",
            json={
                "email": address,
                "organisation_name": "Notified Clinic",
                "tenant_type": "employer",
                "consent_version": CONSENT,
            },
        )
    ).json()["debug_code"]
    tokens = (
        await client.post("/auth/email/otp/verify", json={"email": address, "code": code})
    ).json()
    employer = {"authorization": f"Bearer {tokens['access_token']}"}
    org = tokens["organisation_slug"]
    job = (
        await client.post(
            f"/org/{org}/jobs",
            headers=employer,
            json={
                "title": "Ward Assistant",
                "skills": [
                    {"skill_slug": "notify-standard", "importance": 5, "is_mandatory": True}
                ],
            },
        )
    ).json()
    await client.post(f"/org/{org}/jobs/{job['slug']}/publish", headers=employer)

    phone = "9" + str(uuid.uuid4().int)[:9]
    otp = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    seeker_tokens = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": otp, "consent_version": CONSENT}
        )
    ).json()
    seeker = {"authorization": f"Bearer {seeker_tokens['access_token']}"}
    return {"db": db, "employer": employer, "org": org, "job": job["slug"], "seeker": seeker}


class TestQueueing:
    async def test_applying_queues_the_employer_an_email(
        self, stage: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        await client.post(
            "/me/applications", headers=stage["seeker"], json={"job_slug": stage["job"]}
        )

        row = await db.scalar(
            select(Notification).where(Notification.template == "application_received")
        )
        assert row is not None
        assert row.status == "pending"
        assert row.channel == "email"
        assert row.recipient_kind == "tenant"

    async def test_the_row_holds_no_contact_details(
        self, stage: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The address is resolved at send time. A dumped table, or a log line
        rendering a row, must not carry one (ADR-023)."""
        me = (await client.get("/auth/me", headers=stage["seeker"])).json()
        await client.post(
            "/me/applications", headers=stage["seeker"], json={"job_slug": stage["job"]}
        )

        row = await db.scalar(
            select(Notification).where(Notification.template == "application_received")
        )
        assert row is not None
        blob = str(row.payload)
        assert "@" not in blob
        assert me["phone"] not in blob
        # Nor who applied: that belongs behind the sign-in, on the inbox page.
        assert "candidate" not in blob

    async def test_a_status_change_reaches_the_candidate_in_app_and_by_email(
        self, stage: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        created = (
            await client.post(
                "/me/applications", headers=stage["seeker"], json={"job_slug": stage["job"]}
            )
        ).json()
        await client.patch(
            f"/org/{stage['org']}/jobs/{stage['job']}/applications/{created['id']}",
            headers=stage["employer"],
            json={"status": "shortlisted"},
        )
        rows = (
            await db.scalars(
                select(Notification).where(Notification.template == "application_status_changed")
            )
        ).all()
        assert {r.channel for r in rows} == {"in_app", "email"}
        assert all(r.recipient_kind == "user" for r in rows)


class TestDelivery:
    async def test_a_failing_provider_never_fails_the_application(
        self, stage: dict, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reason this is a queue and not a send: an SMTP timeout while
        somebody applies for a job must not lose the application."""
        import api.modules.notifications.service as notifications

        class Broken:
            async def send_email(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("smtp is down")

        monkeypatch.setattr(notifications, "get_email_provider", lambda: Broken())
        response = await client.post(
            "/me/applications", headers=stage["seeker"], json={"job_slug": stage["job"]}
        )
        assert response.status_code == 201

    async def test_draining_sends_and_marks_sent(
        self, stage: dict, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import api.modules.notifications.service as notifications

        sent: list[tuple[str, str]] = []

        class Recording:
            async def send_email(self, address: str, subject: str, body: str) -> None:
                sent.append((address, subject))

        monkeypatch.setattr(notifications, "get_email_provider", lambda: Recording())
        await client.post(
            "/me/applications", headers=stage["seeker"], json={"job_slug": stage["job"]}
        )

        counts = await drain(db)
        assert counts["sent"] == 1
        assert "@" in sent[0][0]
        assert "Ward Assistant" in sent[0][1]

        db.expire_all()
        row = await db.scalar(
            select(Notification).where(Notification.template == "application_received")
        )
        assert row is not None and row.status == "sent" and row.sent_at is not None

    async def test_no_address_is_skipped_not_failed(
        self, stage: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        """A candidate who signed up with a phone has no email. Nothing is
        wrong with that, and marking it failed would bury the real failures."""
        created = (
            await client.post(
                "/me/applications", headers=stage["seeker"], json={"job_slug": stage["job"]}
            )
        ).json()
        await client.patch(
            f"/org/{stage['org']}/jobs/{stage['job']}/applications/{created['id']}",
            headers=stage["employer"],
            json={"status": "shortlisted"},
        )
        await drain(db)

        db.expire_all()
        row = await db.scalar(
            select(Notification).where(
                Notification.template == "application_status_changed",
                Notification.channel == "email",
            )
        )
        assert row is not None
        assert row.status == "skipped"
        assert row.last_error == "no address on file"

    async def test_a_failure_is_retried_and_eventually_terminal(
        self, stage: dict, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import api.modules.notifications.service as notifications

        class Broken:
            async def send_email(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("smtp is down")

        await client.post(
            "/me/applications", headers=stage["seeker"], json={"job_slug": stage["job"]}
        )
        monkeypatch.setattr(notifications, "get_email_provider", lambda: Broken())

        for _ in range(notifications.MAX_ATTEMPTS):
            await drain(db)

        db.expire_all()
        row = await db.scalar(
            select(Notification).where(Notification.template == "application_received")
        )
        assert row is not None
        assert row.status == "failed"
        assert row.attempts == notifications.MAX_ATTEMPTS
        assert "smtp is down" in (row.last_error or "")


class TestTheCandidatesInbox:
    async def test_listing_and_marking_read(
        self, stage: dict, client: AsyncClient, db: AsyncSession
    ) -> None:
        created = (
            await client.post(
                "/me/applications", headers=stage["seeker"], json={"job_slug": stage["job"]}
            )
        ).json()
        await client.patch(
            f"/org/{stage['org']}/jobs/{stage['job']}/applications/{created['id']}",
            headers=stage["employer"],
            json={"status": "shortlisted"},
        )

        listed = (await client.get("/me/notifications", headers=stage["seeker"])).json()
        assert [n["template"] for n in listed] == ["application_status_changed"]
        assert listed[0]["read_at"] is None
        assert listed[0]["payload"]["status"] == "shortlisted"

        assert (await client.post("/me/notifications/read", headers=stage["seeker"])).json() == {
            "marked": 1
        }
        again = (await client.get("/me/notifications", headers=stage["seeker"])).json()
        assert again[0]["read_at"] is not None

    async def test_nobody_reads_anybody_elses(self, stage: dict, client: AsyncClient) -> None:
        phone = "9" + str(uuid.uuid4().int)[:9]
        code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
        other = (
            await client.post(
                "/auth/otp/verify",
                json={"phone": phone, "code": code, "consent_version": CONSENT},
            )
        ).json()
        headers = {"authorization": f"Bearer {other['access_token']}"}
        assert (await client.get("/me/notifications", headers=headers)).json() == []


def test_a_missing_locale_falls_back_to_english() -> None:
    """Malay has no templates yet. A notice nobody receives because its
    language is missing is worse than one in the wrong language."""
    subject, body = render(
        "application_received", "ms", {"vacancy": "Cashier", "link": "http://x/y"}
    )
    assert "Cashier" in subject
    assert "http://x/y" in body


def test_hindi_templates_are_really_hindi() -> None:
    subject, _ = render("application_received", "hi", {"vacancy": "Cashier", "link": "http://x/y"})
    assert "आवेदन" in subject


async def test_the_queue_starts_empty(db: AsyncSession) -> None:
    assert await db.scalar(select(func.count()).select_from(Notification)) == 0
