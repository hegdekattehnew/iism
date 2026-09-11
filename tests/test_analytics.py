"""Analytics: the two rules that matter, and the one event a client must send.

ADR-025 defers the revenue model and makes measurement the substitute for a
price signal, so this module is load-bearing for a claim the product makes about
itself. It had no test file, and `/me/events/course-opened` was hit by nothing.

Both of `record()`'s rules are the kind that fail silently, which is exactly why
they need asserting: it **commits**, because `get_db_session` never does and a
merely-flushed event is discarded when the request ends; and it **never raises**,
because a broken metric must not take down a page.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics import record
from api.modules.analytics.models import EVENT_NAMES, AnalyticsEvent
from api.modules.identity import Tenant
from api.modules.marketplace.models import Course


@pytest.fixture
async def course(db: AsyncSession) -> Course:
    tenant = Tenant(
        slug="analytics-academy", name="Analytics Academy", tenant_type="course_provider"
    )
    db.add(tenant)
    await db.flush()
    course = Course(
        slug="a-course-worth-clicking",
        tenant_id=tenant.id,
        title_en="A Course Worth Clicking",
        status="published",
    )
    db.add(course)
    await db.commit()
    return course


async def _auth(client: AsyncClient) -> dict[str, str]:
    phone = "9" + uuid.uuid4().int.__str__()[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


async def _count(db: AsyncSession, name: str) -> int:
    return (
        await db.scalar(
            select(func.count()).select_from(AnalyticsEvent).where(AnalyticsEvent.name == name)
        )
    ) or 0


class TestRecord:
    async def test_it_commits(self, db: AsyncSession) -> None:
        """`get_db_session` never commits, so a flushed event is thrown away
        when the request ends. That is exactly what happened the first time this
        was wired up: three `record()` calls a request, and an empty table."""
        await record(db, "matches_viewed", payload={"returned": 0})
        # A fresh query rather than the session's identity map.
        assert await _count(db, "matches_viewed") == 1

    async def test_an_unknown_name_is_dropped_rather_than_raised(self, db: AsyncSession) -> None:
        """Measurement must never be the reason a page fails."""
        await record(db, "not_a_real_event")
        assert await _count(db, "not_a_real_event") == 0

    async def test_the_session_survives_a_rejected_event(self, db: AsyncSession) -> None:
        """The session has to stay usable for whatever the handler does next."""
        await record(db, "not_a_real_event")
        await record(db, "gap_viewed", payload={"missing": 2})
        assert await _count(db, "gap_viewed") == 1

    def test_every_declared_name_is_in_the_check_constraint(self) -> None:
        """Alembic does not diff CHECK bodies, so a name added to `EVENT_NAMES`
        alone is accepted by the model and rejected by the database — and
        `record()` swallows its own failures, so the only symptom is events that
        silently never appear. Migration 0015 exists because of this."""
        body = next(
            c.sqltext.text
            for c in AnalyticsEvent.__table__.constraints
            if getattr(c, "name", None) == "ck_analytics_event_name"
        )
        for name in EVENT_NAMES:
            assert f"'{name}'" in body, name


class TestCourseOpened:
    async def test_a_signed_in_candidate_can_report_a_click(
        self, db: AsyncSession, client: AsyncClient, course: Course
    ) -> None:
        """The one event the server cannot observe for itself: following a link
        out of a recommendation is a client-side act, and inferring it from a
        later course view would credit organic browsing to a recommendation."""
        headers = await _auth(client)
        response = await client.post(
            "/me/events/course-opened",
            headers=headers,
            json={"course_slug": course.slug, "from_job_slug": "some-vacancy"},
        )
        assert response.status_code == 204
        assert await _count(db, "course_opened") == 1

    async def test_it_requires_authentication(self, client: AsyncClient, course: Course) -> None:
        assert (
            await client.post("/me/events/course-opened", json={"course_slug": course.slug})
        ).status_code == 401

    async def test_an_unknown_course_is_a_404(self, client: AsyncClient) -> None:
        headers = await _auth(client)
        assert (
            await client.post(
                "/me/events/course-opened", headers=headers, json={"course_slug": "no-such-course"}
            )
        ).status_code == 404

    async def test_the_payload_carries_slugs_and_nothing_a_person_typed(
        self, db: AsyncSession, client: AsyncClient, course: Course
    ) -> None:
        """ADR-023 keeps resume text, Aadhaar and assessment results out of
        analytics, and a free-form JSON column is where such a thing would leak
        in. This payload is a slug or it is nothing."""
        headers = await _auth(client)
        await client.post(
            "/me/events/course-opened",
            headers=headers,
            json={"course_slug": course.slug, "from_job_slug": "some-vacancy"},
        )
        event = await db.scalar(
            select(AnalyticsEvent).where(AnalyticsEvent.name == "course_opened")
        )
        assert event is not None
        assert event.subject_type == "course"
        assert set(event.payload or {}) <= {"from_job"}
