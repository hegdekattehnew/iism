"""Sprint 45: the same blind spot as Sprint 44, on the paths people use most.

Sprint 44 found that the last-owner guard was a check followed by a write with
nothing between them, and that nothing in the suite could show it, because the
suite runs inside one rolled-back transaction. These tests run two requests
genuinely at once (see `tests/concurrency.py`) against the other check-then-write
paths a phone on mobile data is most likely to hit twice: a double-tap on Apply,
and a candidate withdrawing at the instant an employer decides.

**Two different failures, and they are not equally serious.**

* A double-submit hits a unique constraint, so the data stays right and the second
  request used to get a **500** instead of the "already applied" it would have got
  a moment later.
* Withdrawing against a decision is a **lost update**: both requests pass their
  status check, so whichever writes last wins, and the loser's check was about a
  row that no longer says what it said. That can overwrite an employer's rejection
  (what BL-12.6 exists to prevent) or leave contact visible after a revocation.

Caps -- 50 applications a day, 20 pending invitations, 60 skills -- are
**deliberately not locked**. They deter abuse rather than guard an invariant, and
serialising every application per candidate to turn "about 50" into "exactly 50"
would trade throughput for a precision nothing depends on.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from api.core.database import get_sessionmaker
from api.modules.applications import Application, SavedJob
from api.modules.interests.models import CourseInterest
from api.modules.notifications.models import Notification
from tests.concurrency import (
    World,
    build_world,
    candidate,
    real_client,
    row_locked,
    tear_down,
    wait_until_blocked,
)


@pytest.fixture
async def world() -> AsyncIterator[tuple[AsyncClient, World]]:
    async with real_client() as client:
        built = await build_world(client)
        try:
            yield client, built
        finally:
            await tear_down(client, built)


async def _new_candidate(client: AsyncClient, built: World) -> dict[str, str]:
    headers = await candidate(client)
    built.candidates.append(headers)
    return headers


def _slow(module: object, name: str, monkeypatch: pytest.MonkeyPatch, seconds: float = 0.4) -> None:
    """Hold a function open for a moment after it answers, widening the window
    between a check and the write that depends on it."""
    original = getattr(module, name)

    async def slow(*args: object, **kwargs: object) -> object:
        result = await original(*args, **kwargs)
        await asyncio.sleep(seconds)
        return result

    monkeypatch.setattr(module, name, slow)


async def _count(model: type, **where: object) -> int:
    async with get_sessionmaker()() as db:
        query = select(func.count()).select_from(model)
        for column, value in where.items():
            query = query.where(getattr(model, column) == value)
        return (await db.scalar(query)) or 0


class TestDoubleSubmit:
    async def test_applying_twice_at_once_is_a_201_and_a_409_never_a_500(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.modules.applications import service

        client, built = world
        headers = await _new_candidate(client, built)
        _slow(service, "_within_daily_cap", monkeypatch)

        body = {"job_slug": built.job_slug}
        first, second = await asyncio.gather(
            client.post("/me/applications", headers=headers, json=body),
            client.post("/me/applications", headers=headers, json=body),
        )

        assert sorted([first.status_code, second.status_code]) == [201, 409]
        assert await _count(Application) >= 1
        applied = (await client.get("/me/applications", headers=headers)).json()
        assert len(applied) == 1

    async def test_reapplying_after_a_withdrawal_twice_at_once_notifies_the_employer_once(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No unique violation here -- both requests find the same withdrawn row --
        so without a lock both 'succeed' and the employer is emailed twice."""
        from api.modules.applications import service

        client, built = world
        headers = await _new_candidate(client, built)
        body = {"job_slug": built.job_slug}
        first_apply = await client.post("/me/applications", headers=headers, json=body)
        application_id = first_apply.json()["id"]
        await client.post(f"/me/applications/{application_id}/withdraw", headers=headers)
        async with get_sessionmaker()() as db:
            before = await db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.template == "application_received")
            )
        _slow(service, "_within_daily_cap", monkeypatch)

        a, b = await asyncio.gather(
            client.post("/me/applications", headers=headers, json=body),
            client.post("/me/applications", headers=headers, json=body),
        )

        assert sorted([a.status_code, b.status_code]) == [201, 409]
        async with get_sessionmaker()() as db:
            after = await db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.template == "application_received")
            )
        assert (after or 0) - (before or 0) == 1

    async def test_registering_interest_twice_at_once_is_a_201_and_a_409(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.modules.interests import service

        client, built = world
        headers = await _new_candidate(client, built)
        _slow(service, "_within_daily_cap", monkeypatch)

        body = {"course_slug": built.course_slug}
        a, b = await asyncio.gather(
            client.post("/me/course-interests", headers=headers, json=body),
            client.post("/me/course-interests", headers=headers, json=body),
        )

        assert sorted([a.status_code, b.status_code]) == [201, 409]
        assert len((await client.get("/me/course-interests", headers=headers)).json()) == 1

    async def test_saving_a_vacancy_twice_at_once_is_idempotent_not_a_500(
        self, world: tuple[AsyncClient, World], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from api.modules.applications import service

        client, built = world
        headers = await _new_candidate(client, built)
        _slow(service, "_published_job", monkeypatch)

        body = {"job_slug": built.job_slug}
        a, b = await asyncio.gather(
            client.post("/me/saved-jobs", headers=headers, json=body),
            client.post("/me/saved-jobs", headers=headers, json=body),
        )

        assert a.status_code < 300 and b.status_code < 300, (a.text, b.text)
        assert len((await client.get("/me/saved-jobs", headers=headers)).json()) == 1
        assert await _count(SavedJob) >= 1


async def _applied(client: AsyncClient, built: World) -> tuple[dict[str, str], str]:
    headers = await _new_candidate(client, built)
    response = await client.post(
        "/me/applications", headers=headers, json={"job_slug": built.job_slug}
    )
    assert response.status_code == 201, response.text
    return headers, response.json()["id"]


async def _interested(client: AsyncClient, built: World) -> tuple[dict[str, str], str]:
    headers = await _new_candidate(client, built)
    response = await client.post(
        "/me/course-interests", headers=headers, json={"course_slug": built.course_slug}
    )
    assert response.status_code == 201, response.text
    return headers, response.json()["id"]


async def _both_in_flight_then_released(
    model: type,
    row_id: str,
    first: Callable[[], Awaitable[Response]],
    second: Callable[[], Awaitable[Response]],
) -> tuple[Response, Response]:
    async with row_locked(model, uuid.UUID(row_id)):
        tasks = [asyncio.create_task(first()), asyncio.create_task(second())]
        await wait_until_blocked(2)
    a, b = await asyncio.gather(*tasks)
    return a, b


class TestWithdrawingAgainstADecision:
    @pytest.mark.parametrize("decision", ["rejected", "shortlisted", "hired"])
    async def test_exactly_one_of_withdraw_and_decide_wins(
        self, world: tuple[AsyncClient, World], decision: str
    ) -> None:
        """Both pass their status check, then queue behind the same row. Without a
        lock both then write and both report success, so a rejection can be
        overwritten by a withdrawal -- or contact can be left visible on a row the
        candidate has revoked. With one, the second request re-reads and is refused."""
        client, built = world
        headers, application_id = await _applied(client, built)

        withdraw, decide = await _both_in_flight_then_released(
            Application,
            application_id,
            lambda: client.post(f"/me/applications/{application_id}/withdraw", headers=headers),
            lambda: client.patch(
                f"/org/{built.employer_slug}/jobs/{built.job_slug}/applications/{application_id}",
                headers=built.employer,
                json={"status": decision},
            ),
        )

        if decision == "shortlisted":
            # Not a final decision: shortlisting and then withdrawing is a legal
            # order, so both may succeed -- provided the withdrawal is the last word.
            assert {withdraw.status_code, decide.status_code} <= {200, 409}
            both = withdraw.status_code == decide.status_code == 200
        else:
            # Rejected and hired are the employer's record. Whoever is second sees
            # the first's result: a withdrawal after a decision is refused, and a
            # decision after a withdrawal is refused.
            assert {withdraw.status_code, decide.status_code} == {200, 409}, (
                withdraw.status_code,
                decide.status_code,
            )
            both = False

        async with get_sessionmaker()() as db:
            row = await db.get(Application, uuid.UUID(application_id))
            assert row is not None
            await db.refresh(row)
            if both:
                assert row.status == "withdrawn"
            if row.status == "withdrawn":
                assert row.contact_revoked_at is not None
            else:
                assert row.contact_revoked_at is None, (
                    "contact was revoked but the row says " + row.status
                )

    async def test_the_same_for_a_learner_and_a_provider(
        self, world: tuple[AsyncClient, World]
    ) -> None:
        client, built = world
        headers, interest_id = await _interested(client, built)

        withdraw, mark = await _both_in_flight_then_released(
            CourseInterest,
            interest_id,
            lambda: client.post(f"/me/course-interests/{interest_id}/withdraw", headers=headers),
            lambda: client.patch(
                f"/org/{built.provider_slug}/courses/{built.course_slug}/interests/{interest_id}",
                headers=built.provider,
                json={"status": "contacted"},
            ),
        )

        # Withdrawing is idempotent (it answers 200 whether or not it did the
        # work), so the refusal to look for is the provider's.
        assert withdraw.status_code == 200, withdraw.text
        async with get_sessionmaker()() as db:
            row = await db.get(CourseInterest, uuid.UUID(interest_id))
            assert row is not None
            await db.refresh(row)
            assert row.status == "withdrawn" or row.contact_revoked_at is None
            if mark.status_code == 200:
                # The provider won the lock, so the learner's withdrawal came
                # second and is the final word.
                assert row.status == "withdrawn" and row.contact_revoked_at is not None
            else:
                assert mark.status_code == 409
                assert row.status == "withdrawn"
