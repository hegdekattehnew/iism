"""Pushing an in-app notice to a person's phone (Sprint 65, BL-15.6, ADR-075).

What is worth pinning is not that a message is sent but what it may carry and who it may reach: a
push is shown on a lock screen and kept by the operating system, so **nothing from a notice's
payload reaches its title, body or data** beyond an in-app path; no row holds a token; a person with
no phone costs a stamp and nothing else; and queuing a notice adds no work to the request.
"""

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.push import ConsolePushProvider, InvalidDeviceToken
from api.modules.notifications import DeviceToken, Notification, drain, enqueue, enqueue_many
from api.modules.notifications import service as notifications_service
from api.modules.notifications.service import (
    MAX_ATTEMPTS,
    PUSH_WINDOW,
    list_for,
    unread_count,
)
from api.modules.notifications.templates import PUSH_TEXT, push_data, push_text
from tests.test_operations import _candidate

SECRET = "Confidential Cardiac Ward Vacancy"
ORG = "Hidden Hospital Trust"
PAYLOAD = {"vacancy": SECRET, "organisation": ORG, "status": "shortlisted", "path": "/applications"}


class Recorder:
    """A push provider that remembers what it was asked to send, and can be told to fail."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str, dict[str, str]]] = []
        self.dead: set[str] = set()
        self.broken = False

    async def send_push(self, token: str, title: str, body: str, data: Mapping[str, str]) -> None:
        if token in self.dead:
            raise InvalidDeviceToken(token)
        if self.broken:
            raise RuntimeError("provider is down")
        self.sent.append((token, title, body, dict(data)))


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorder = Recorder()
    monkeypatch.setattr(notifications_service, "get_push_provider", lambda: recorder)
    return recorder


async def _person(client: AsyncClient) -> uuid.UUID:
    headers = await _candidate(client)
    return uuid.UUID((await client.get("/auth/me", headers=headers)).json()["id"])


async def _give_phone(db: AsyncSession, user_id: uuid.UUID, token: str | None = None) -> str:
    token = token or f"ExponentPushToken[{uuid.uuid4().hex}]"
    db.add(DeviceToken(user_id=user_id, token=token, platform="android", locale="en"))
    await db.flush()
    return token


async def _tell(
    db: AsyncSession,
    user_id: uuid.UUID,
    template: str = "application_status_changed",
    *,
    recipient_kind: str = "user",
    channel: str = "in_app",
    payload: dict[str, object] | None = None,
    locale: str = "en",
) -> Notification:
    notice = await enqueue(
        db,
        recipient_kind=recipient_kind,
        recipient_id=user_id,
        channel=channel,
        template=template,
        payload=payload or PAYLOAD,
        locale=locale,
    )
    await db.flush()
    return notice


async def _fresh(db: AsyncSession, notice: Notification) -> Notification:
    await db.refresh(notice)
    return notice


class TestQueuingCostsNothingExtra:
    async def test_queuing_notices_runs_no_query(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """The first design looked for a phone as each notice was queued, which a loop that
        queues a hundred (the alert sweep) paid a hundred times; a statement-count test caught it.
        The worker decides; queuing does not ask."""
        user = await _person(client)
        await _give_phone(db, user)
        statements: list[str] = []

        def count(conn, cursor, statement, *rest):  # type: ignore[no-untyped-def]
            statements.append(statement)

        engine = db.bind.sync_engine  # type: ignore[union-attr]
        event.listen(engine, "before_cursor_execute", count)
        try:
            for _ in range(20):
                await enqueue(
                    db,
                    recipient_kind="user",
                    recipient_id=user,
                    channel="in_app",
                    template="application_status_changed",
                    payload=PAYLOAD,
                )
        finally:
            event.remove(engine, "before_cursor_execute", count)
        assert [s for s in statements if s.lstrip().upper().startswith("SELECT")] == []


class TestWhoIsPushed:
    async def test_a_person_with_a_phone_is_pushed_and_the_notice_is_stamped(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        token = await _give_phone(db, user)
        notice = await _tell(db, user)
        await drain(db)
        assert [p[0] for p in provider.sent] == [token]
        assert (await _fresh(db, notice)).pushed_at is not None

    async def test_a_person_without_one_costs_a_stamp_and_nothing_is_sent(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        notice = await _tell(db, user)
        await drain(db)
        assert provider.sent == []
        assert (await _fresh(db, notice)).pushed_at is not None

    async def test_a_phone_registered_afterwards_is_not_sent_what_it_missed(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        await _tell(db, user)
        await drain(db)
        await _give_phone(db, user)
        await drain(db)
        assert provider.sent == []

    async def test_a_notice_is_pushed_once(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        await _give_phone(db, user)
        await _tell(db, user)
        await drain(db)
        await drain(db)
        assert len(provider.sent) == 1

    async def test_an_email_an_organisation_and_an_invitee_are_never_pushed(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        await _give_phone(db, user)
        notices = [
            await _tell(db, user, channel="email"),
            await _tell(db, user, recipient_kind="tenant"),
            await _tell(db, user, recipient_kind="invitation"),
        ]
        await drain(db)
        assert provider.sent == []
        for notice in notices:
            assert (await _fresh(db, notice)).pushed_at is None

    async def test_a_template_with_no_push_words_is_stamped_and_not_sent(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        await _give_phone(db, user)
        notice = await _tell(db, user, template="organisation_invitation")
        await drain(db)
        assert provider.sent == []
        assert (await _fresh(db, notice)).pushed_at is not None

    async def test_the_bulk_path_is_pushed_too(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        with_phone, without = await _person(client), await _person(client)
        token = await _give_phone(db, with_phone)
        base = {
            "recipient_kind": "user",
            "channel": "in_app",
            "template": "vacancy_closed",
            "payload": {"vacancy": SECRET, "path": "/applications"},
        }
        await enqueue_many(
            db, [{**base, "recipient_id": with_phone}, {**base, "recipient_id": without}]
        )
        await db.flush()
        await drain(db)
        assert [p[0] for p in provider.sent] == [token]

    async def test_a_notice_older_than_the_window_is_stamped_not_sent(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        """Switching push on, or a worker that was down, must not replay a backlog."""
        user = await _person(client)
        await _give_phone(db, user)
        notice = await _tell(db, user)
        await db.execute(
            update(Notification)
            .where(Notification.id == notice.id)
            .values(created_at=datetime.now(UTC) - PUSH_WINDOW - timedelta(hours=1))
        )
        await drain(db)
        assert provider.sent == []
        assert (await _fresh(db, notice)).pushed_at is not None

    async def test_pushing_changes_nothing_in_the_in_app_list_or_its_count(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        await _give_phone(db, user)
        await _tell(db, user)
        await drain(db)
        listed = await list_for(db, user)
        assert len(listed) == 1 and listed[0].read_at is None
        assert await unread_count(db, user) == 1


class TestWhatAPushMayCarry:
    async def test_nothing_from_the_payload_reaches_the_title_the_body_or_the_data(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        token = await _give_phone(db, user)
        await _tell(db, user)
        await drain(db)
        pushes = [p for p in provider.sent if p[0] == token]
        assert len(pushes) == 1
        _, title, body, data = pushes[0]
        everything = json.dumps([title, body, data])
        assert SECRET not in everything
        assert ORG not in everything
        assert "shortlisted" not in everything
        assert (title, body) == push_text("application_status_changed", "en")
        assert data == {"template": "application_status_changed", "path": "/applications"}

    async def test_it_speaks_the_language_the_notice_was_queued_in(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        await _give_phone(db, user)
        await _tell(db, user, locale="hi")
        await drain(db)
        assert provider.sent[-1][1:3] == push_text("application_status_changed", "hi")
        assert provider.sent[-1][1] != push_text("application_status_changed", "en")[0]

    @pytest.mark.parametrize(
        "path", ["//evil.example/x", "https://evil.example", "relative", 5, None]
    )
    def test_a_path_that_leaves_the_app_is_dropped(self, path: object) -> None:
        assert push_data("job_alert", {"path": path}) == {"template": "job_alert"}

    def test_a_grievance_update_points_at_its_fixed_page(self) -> None:
        assert push_data("grievance_update", {"reference": "G-1"}) == {
            "template": "grievance_update",
            "path": "/grievance",
        }

    def test_every_template_with_push_words_has_them_in_both_languages(self) -> None:
        assert set(PUSH_TEXT["en"]) == set(PUSH_TEXT["hi"]) and len(PUSH_TEXT["en"]) >= 6
        for table in PUSH_TEXT.values():
            for title, body in table.values():
                # A format field here would be a payload value on a lock screen.
                assert "{" not in title and "{" not in body

    async def test_no_row_holds_a_token(self, client: AsyncClient, db: AsyncSession) -> None:
        user = await _person(client)
        token = await _give_phone(db, user)
        await _tell(db, user)
        rows = (
            await db.scalars(select(Notification).where(Notification.recipient_id == user))
        ).all()
        assert token not in json.dumps([[r.payload, r.last_error, r.channel] for r in rows])


class TestDelivery:
    async def test_a_dead_token_is_deleted_and_a_live_one_still_gets_it(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        dead = await _give_phone(db, user)
        live = await _give_phone(db, user)
        provider.dead.add(dead)
        notice = await _tell(db, user)
        await drain(db)
        held = (
            await db.scalars(select(DeviceToken.token).where(DeviceToken.user_id == user))
        ).all()
        assert list(held) == [live]
        assert [p[0] for p in provider.sent] == [live]
        assert (await _fresh(db, notice)).pushed_at is not None

    async def test_only_dead_tokens_leave_nothing_held_and_the_notice_stamped(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        provider.dead.add(await _give_phone(db, user))
        notice = await _tell(db, user)
        await drain(db)
        count = await db.scalar(
            select(func.count()).select_from(DeviceToken).where(DeviceToken.user_id == user)
        )
        assert count == 0
        assert (await _fresh(db, notice)).pushed_at is not None

    async def test_an_outage_retries_then_gives_up_and_keeps_the_token(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        token = await _give_phone(db, user)
        provider.broken = True
        notice = await _tell(db, user)
        stamped = []
        for _ in range(MAX_ATTEMPTS):
            await drain(db)
            stamped.append((await _fresh(db, notice)).pushed_at is not None)
        assert stamped[:-1] == [False] * (MAX_ATTEMPTS - 1) and stamped[-1] is True
        assert (await _fresh(db, notice)).attempts == MAX_ATTEMPTS
        held = (
            await db.scalars(select(DeviceToken.token).where(DeviceToken.user_id == user))
        ).all()
        assert list(held) == [token]

    async def test_a_push_outage_never_fails_the_email_that_shares_the_drain(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        await _give_phone(db, user)
        provider.broken = True
        await _tell(db, user)
        email = await _tell(db, user, channel="email")
        counts = await drain(db)
        assert counts["failed"] == 0
        assert (await _fresh(db, email)).status in {"sent", "skipped"}

    async def test_a_failed_push_leaves_the_in_app_notice_readable(
        self, client: AsyncClient, db: AsyncSession, provider: Recorder
    ) -> None:
        user = await _person(client)
        await _give_phone(db, user)
        provider.broken = True
        await _tell(db, user)
        await drain(db)
        assert len(await list_for(db, user)) == 1


class TestTheConsoleProvider:
    async def test_it_logs_a_digest_and_never_the_token(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        token = "ExponentPushToken[should-never-be-logged]"
        await ConsolePushProvider().send_push(token, "t", "b", {"template": "x"})
        out = capsys.readouterr()
        assert token not in out.out + out.err

    async def test_it_refuses_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Production:
            is_local = False

        monkeypatch.setattr("api.adapters.push.console.get_settings", lambda: Production())
        with pytest.raises(RuntimeError, match="No push provider"):
            await ConsolePushProvider().send_push("ExponentPushToken[abc]", "t", "b", {})
