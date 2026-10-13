"""A way to complain (Sprint 57, BL-14.3, ADR-067).

The grievance page promised "we acknowledge within 24 hours and aim to resolve it within 15 days"
and told people to write to an officer, and there was no form, no table and nobody reading anything.
These pin the rules a public endpoint that writes a row needs: who may send what, that we never
write to an address a stranger typed, a budget and a honeypot, a promise the queue can measure, and
a record that is deleted when its time is up and not before.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.cache import get_redis
from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.core.config import get_settings
from api.modules.grievances import Grievance, purge_expired
from api.modules.grievances import service as grievance_service
from api.modules.identity.models import User
from api.modules.notifications.models import Notification

PATH = "/grievances"
GOOD = "My employer shared my number outside the vacancy I applied to."


def _phone() -> str:
    return "9" + str(uuid.uuid4().int)[:9]


def _email() -> str:
    return f"grv-{uuid.uuid4().hex[:10]}@iism-fixtures.co.in"


async def _signed_in(client: AsyncClient, *, email: bool = False) -> tuple[dict[str, str], str]:
    phone = _phone()
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    tokens = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    headers = {"authorization": f"Bearer {tokens['access_token']}"}
    if email:
        address = _email()
        code = (
            await client.post("/me/credentials/email", headers=headers, json={"email": address})
        ).json()["debug_code"]
        await client.post(
            "/me/credentials/email/verify", headers=headers, json={"email": address, "code": code}
        )
        return headers, address
    return headers, phone


async def _operator(client: AsyncClient, db: AsyncSession, tier: str = "support") -> dict[str, str]:
    headers, _ = await _signed_in(client)
    me = (await client.get("/auth/me", headers=headers)).json()
    user = await db.get(User, uuid.UUID(me["id"]))
    assert user is not None
    user.is_staff, user.staff_tier = True, tier
    await db.commit()
    return headers


async def _send(client: AsyncClient, **body: object) -> object:
    payload = {"kind": "contact", "body": GOOD, "reply_to": _email(), **body}
    headers = payload.pop("headers", None)  # type: ignore[arg-type]
    return await client.post(PATH, json=payload, headers=headers)  # type: ignore[arg-type]


class Mailbox:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = False

    async def send_email(self, address: str, subject: str, body: str) -> None:
        if self.fail:
            raise RuntimeError("provider down")
        self.sent.append((address, subject, body))


@pytest.fixture
def mailbox(monkeypatch: pytest.MonkeyPatch) -> Iterator[Mailbox]:
    box = Mailbox()
    monkeypatch.setattr(grievance_service, "get_email_provider", lambda: box)
    yield box


async def _count(db: AsyncSession) -> int:
    return (await db.scalar(select(func.count()).select_from(Grievance))) or 0


class TestWhoMaySendWhat:
    async def test_a_stranger_may_write_to_us_and_gets_a_reference(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        address = _email().upper()
        response = await client.post(
            PATH, json={"kind": "contact", "body": GOOD, "reply_to": address}
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["reference"].startswith("GRV-") and len(body["reference"]) == 10
        assert (body["acknowledge_within_hours"], body["resolve_within_days"]) == (24, 15)
        row = await db.scalar(select(Grievance).where(Grievance.reference == body["reference"]))
        assert row is not None and row.user_id is None
        assert row.reply_to == address.lower()  # the form every other address here is held in

    async def test_a_mobile_number_is_a_reply_address_too_and_is_held_in_one_form(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        response = await client.post(
            PATH, json={"kind": "grievance", "body": GOOD, "reply_to": "098765 43210"}
        )
        assert response.status_code == 201
        row = await db.scalar(select(Grievance).order_by(Grievance.created_at.desc()))
        assert row is not None and row.reply_to == "+919876543210"

    @pytest.mark.parametrize("reply_to", [None, "", "   ", "not an address", "12345"])
    async def test_a_stranger_must_leave_something_to_write_back_to(
        self, client: AsyncClient, reply_to: str | None
    ) -> None:
        body = {"kind": "grievance", "body": GOOD}
        if reply_to is not None:
            body["reply_to"] = reply_to
        assert (await client.post(PATH, json=body)).status_code == 422

    async def test_a_request_about_your_data_needs_you_signed_in(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        before = await _count(db)
        refused = await client.post(
            PATH, json={"kind": "data_request", "body": GOOD, "reply_to": _email()}
        )
        assert refused.status_code == 401 and "Sign in" in refused.json()["detail"]
        assert await _count(db) == before

        headers, _ = await _signed_in(client)
        allowed = await client.post(
            PATH, json={"kind": "data_request", "body": GOOD}, headers=headers
        )
        assert allowed.status_code == 201
        row = await db.scalar(
            select(Grievance).where(Grievance.reference == allowed.json()["reference"])
        )
        assert row is not None and row.user_id is not None and row.reply_to is None

    async def test_a_signed_in_sender_is_answered_through_their_account_not_a_stored_address(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, _ = await _signed_in(client)
        response = await client.post(
            PATH, json={"kind": "contact", "body": GOOD, "reply_to": _email()}, headers=headers
        )
        row = await db.scalar(
            select(Grievance).where(Grievance.reference == response.json()["reference"])
        )
        assert row is not None and row.reply_to is None

    @pytest.mark.parametrize("body", ["", "too short", "x" * 4001])
    async def test_the_message_has_a_floor_and_a_ceiling(
        self, client: AsyncClient, body: str
    ) -> None:
        response = await client.post(
            PATH, json={"kind": "contact", "body": body, "reply_to": _email()}
        )
        assert response.status_code == 422

    async def test_the_database_holds_the_same_rule_without_the_service(
        self, db: AsyncSession
    ) -> None:
        db.add(
            Grievance(
                reference="GRV-TESTAA", kind="data_request", body=GOOD, reply_to="a@b.example"
            )
        )
        with pytest.raises(IntegrityError):
            await db.flush()


class TestNoRelay:
    async def test_the_address_a_stranger_typed_is_never_written_to(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        assert (await _send(client)).status_code == 201  # type: ignore[attr-defined]
        assert mailbox.sent == []

    async def test_a_signed_in_sender_is_acknowledged_at_the_address_their_account_holds(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        headers, address = await _signed_in(client, email=True)
        mailbox.sent.clear()
        response = await client.post(
            PATH,
            json={"kind": "grievance", "body": GOOD, "reply_to": "elsewhere@example.org"},
            headers=headers,
        )
        reference = response.json()["reference"]
        assert [m[0] for m in mailbox.sent] == [address]
        assert reference in mailbox.sent[0][1] and GOOD not in mailbox.sent[0][2]

    async def test_a_phone_only_sender_has_no_address_to_write_to_and_the_message_still_lands(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        headers, _ = await _signed_in(client)
        response = await client.post(PATH, json={"kind": "contact", "body": GOOD}, headers=headers)
        assert response.status_code == 201 and mailbox.sent == []

    async def test_a_failing_provider_never_undoes_the_message(
        self, client: AsyncClient, db: AsyncSession, mailbox: Mailbox
    ) -> None:
        headers, _ = await _signed_in(client, email=True)
        mailbox.fail = True
        response = await client.post(PATH, json={"kind": "contact", "body": GOOD}, headers=headers)
        assert response.status_code == 201
        assert await db.scalar(
            select(Grievance).where(Grievance.reference == response.json()["reference"])
        )


class TestAPublicEndpointThatWritesARow:
    async def test_the_honeypot_answers_success_and_keeps_nothing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        before = await _count(db)
        response = await client.post(
            PATH,
            json={"kind": "contact", "body": GOOD, "reply_to": _email(), "website": "http://spam"},
        )
        assert response.status_code == 201 and response.json()["reference"].startswith("GRV-")
        assert await _count(db) == before
        assert (
            await db.scalar(
                select(Grievance).where(Grievance.reference == response.json()["reference"])
            )
            is None
        )

    async def test_the_budget_stops_a_flood_and_says_when_to_come_back(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRIEVANCE_SUBMISSIONS_PER_HOUR", "3")
        get_settings.cache_clear()
        redis = get_redis()
        for key in await redis.keys("budget:grievance-*"):
            await redis.delete(key)
        try:
            codes = [(await _send(client)).status_code for _ in range(5)]  # type: ignore[attr-defined]
            assert codes == [201, 201, 201, 429, 429]
            limited = await _send(client)
            assert int(limited.headers["retry-after"]) > 0  # type: ignore[attr-defined]
        finally:
            for key in await redis.keys("budget:grievance-*"):
                await redis.delete(key)
            monkeypatch.delenv("GRIEVANCE_SUBMISSIONS_PER_HOUR")
            get_settings.cache_clear()

    async def test_the_two_budgets_are_independent_one_per_address_one_per_sender(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One person on a shared address must not lock out their neighbours, and one person
        changing address must not escape their own budget."""
        monkeypatch.setenv("GRIEVANCE_SUBMISSIONS_PER_HOUR", "2")
        monkeypatch.setenv("RATE_LIMIT_TRUST_FORWARDED", "true")
        get_settings.cache_clear()
        redis = get_redis()
        try:
            home = f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.7"
            elsewhere = f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.9"

            def at(ip: str, reply_to: str) -> object:
                return client.post(
                    PATH,
                    json={"kind": "contact", "body": GOOD, "reply_to": reply_to},
                    headers={"x-forwarded-for": ip},
                )

            # Same address, different senders: the address runs out, another address does not.
            codes = [(await at(home, _email())).status_code for _ in range(3)]  # type: ignore[attr-defined]
            assert codes == [201, 201, 429]
            assert (await at(elsewhere, _email())).status_code == 201  # type: ignore[attr-defined]

            # Same sender, a fresh address each time: the sender runs out.
            same = _email()
            fresh = [
                (await at(f"10.{i}.{uuid.uuid4().int % 250}.1", same)).status_code  # type: ignore[attr-defined]
                for i in range(3)
            ]
            assert fresh == [201, 201, 429]
        finally:
            for key in await redis.keys("budget:grievance-*"):
                await redis.delete(key)
            monkeypatch.delenv("GRIEVANCE_SUBMISSIONS_PER_HOUR")
            monkeypatch.delenv("RATE_LIMIT_TRUST_FORWARDED")
            get_settings.cache_clear()

    async def test_a_taken_reference_is_drawn_again(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        draws = iter(["GRV-AAAAAA", "GRV-AAAAAA", "GRV-BBBBBB"])
        monkeypatch.setattr(grievance_service, "_new_reference", lambda: next(draws))
        first = await _send(client)
        second = await _send(client)
        assert (first.json()["reference"], second.json()["reference"]) == (
            "GRV-AAAAAA",
            "GRV-BBBBBB",
        )  # type: ignore[attr-defined]


class TestTheQueue:
    async def _three(self, client: AsyncClient, db: AsyncSession) -> list[Grievance]:
        out = []
        for kind in ("contact", "grievance", "grievance"):
            ref = (await _send(client, kind=kind)).json()["reference"]  # type: ignore[attr-defined]
            out.append(await db.scalar(select(Grievance).where(Grievance.reference == ref)))
        return [g for g in out if g is not None]

    async def test_it_is_for_operators_of_either_tier_and_nobody_else(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        for tier in ("support", "admin"):
            headers = await _operator(client, db, tier)
            assert (await client.get("/ops/grievances", headers=headers)).status_code == 200
        stranger, _ = await _signed_in(client)
        assert (await client.get("/ops/grievances", headers=stranger)).status_code == 404

    async def test_open_first_and_the_one_that_has_waited_longest_first(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        a, b, c = await self._three(client, db)
        now = datetime.now(UTC)
        a.created_at, b.created_at, c.created_at = (
            now - timedelta(hours=1),
            now - timedelta(hours=5),
            now - timedelta(hours=3),
        )
        c.status, c.acknowledged_at = "acknowledged", now
        await db.commit()
        headers = await _operator(client, db)
        refs = [
            i["reference"]
            for i in (await client.get("/ops/grievances", headers=headers)).json()["items"]
        ]
        mine = [r for r in refs if r in {a.reference, b.reference, c.reference}]
        assert mine == [b.reference, a.reference, c.reference]

    async def test_overdue_is_read_from_the_promise_and_a_contact_message_promises_nothing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        contact, late, resolve_late = await self._three(client, db)
        now = datetime.now(UTC)
        contact.created_at = now - timedelta(days=30)
        late.created_at = now - timedelta(hours=30)
        resolve_late.created_at = now - timedelta(days=16)
        resolve_late.status, resolve_late.acknowledged_at = "acknowledged", now - timedelta(days=15)
        await db.commit()
        headers = await _operator(client, db)
        body = (await client.get("/ops/grievances", headers=headers)).json()
        by_ref = {i["reference"]: i for i in body["items"]}
        assert not by_ref[contact.reference]["overdue_acknowledge"]
        assert not by_ref[contact.reference]["overdue_resolve"]
        assert (
            by_ref[late.reference]["overdue_acknowledge"]
            and not by_ref[late.reference]["overdue_resolve"]
        )
        assert by_ref[resolve_late.reference]["overdue_resolve"]
        assert not by_ref[resolve_late.reference]["overdue_acknowledge"], "it was acknowledged"
        assert body["overdue"] >= 2 and body["open"] >= 3

    async def test_the_deadlines_are_the_settings_not_a_second_copy_of_them(
        self, client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        g = (await self._three(client, db))[1]
        g.created_at = datetime.now(UTC) - timedelta(hours=2)
        await db.commit()
        headers = await _operator(client, db)
        item = lambda body: next(i for i in body["items"] if i["reference"] == g.reference)  # noqa: E731
        assert not item((await client.get("/ops/grievances", headers=headers)).json())[
            "overdue_acknowledge"
        ]
        monkeypatch.setenv("GRIEVANCE_ACKNOWLEDGE_HOURS", "1")
        get_settings.cache_clear()
        try:
            assert item((await client.get("/ops/grievances", headers=headers)).json())[
                "overdue_acknowledge"
            ]
        finally:
            monkeypatch.delenv("GRIEVANCE_ACKNOWLEDGE_HOURS")
            get_settings.cache_clear()

    async def test_a_signed_in_senders_account_is_shown_masked_and_a_strangers_address_as_given(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        sender, address = await _signed_in(client, email=True)
        me = (await client.get("/auth/me", headers=sender)).json()
        phone = me["phone"]
        ref = (
            await client.post(PATH, json={"kind": "grievance", "body": GOOD}, headers=sender)
        ).json()["reference"]
        stranger_address = _email()
        other = (await _send(client, reply_to=stranger_address)).json()["reference"]  # type: ignore[attr-defined]
        headers = await _operator(client, db)
        raw = await client.get("/ops/grievances", headers=headers)
        items = {i["reference"]: i for i in raw.json()["items"]}
        assert phone not in raw.text and address not in raw.text
        assert "*" in items[ref]["account"]["phone"] and "*" in items[ref]["account"]["email"]
        assert items[other]["reply_to"] == stranger_address.lower()
        assert items[other]["account"] is None


class TestDecisions:
    async def _one(
        self, client: AsyncClient, db: AsyncSession, **kw: object
    ) -> tuple[Grievance, dict[str, str]]:
        ref = (await _send(client, kind="grievance", **kw)).json()["reference"]  # type: ignore[attr-defined]
        g = await db.scalar(select(Grievance).where(Grievance.reference == ref))
        assert g is not None
        return g, await _operator(client, db)

    async def test_acknowledge_then_resolve_and_a_closed_one_is_final(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        g, ops = await self._one(client, db)
        acked = await client.post(f"/ops/grievances/{g.id}/acknowledge", headers=ops)
        assert acked.status_code == 200 and acked.json()["status"] == "acknowledged"
        assert (
            await client.post(f"/ops/grievances/{g.id}/acknowledge", headers=ops)
        ).status_code == 409

        resolved = await client.post(
            f"/ops/grievances/{g.id}/resolve",
            headers=ops,
            json={"note": "Wrote back; employer told to stop."},
        )
        assert resolved.status_code == 200 and resolved.json()["resolved_at"]
        for verb in ("resolve", "dismiss"):
            again = await client.post(
                f"/ops/grievances/{g.id}/{verb}", headers=ops, json={"note": "x" * 12}
            )
            assert again.status_code == 409

    async def test_closing_an_open_one_acknowledges_it_and_needs_a_real_note(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        g, ops = await self._one(client, db)
        assert (
            await client.post(
                f"/ops/grievances/{g.id}/dismiss", headers=ops, json={"note": "short"}
            )
        ).status_code == 422
        done = await client.post(
            f"/ops/grievances/{g.id}/dismiss", headers=ops, json={"note": "Not about this product."}
        )
        body = done.json()
        assert body["status"] == "dismissed" and body["acknowledged_at"] and body["resolved_at"]

    async def test_a_signed_in_sender_is_told_on_each_change_and_never_given_the_note(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        sender, _ = await _signed_in(client)
        ref = (
            await client.post(PATH, json={"kind": "grievance", "body": GOOD}, headers=sender)
        ).json()["reference"]
        g = await db.scalar(select(Grievance).where(Grievance.reference == ref))
        ops = await _operator(client, db)
        await client.post(f"/ops/grievances/{g.id}/acknowledge", headers=ops)
        await client.post(
            f"/ops/grievances/{g.id}/resolve",
            headers=ops,
            json={"note": "Internal: the employer is Mr Rao."},
        )
        rows = (
            await db.scalars(
                select(Notification).where(
                    Notification.recipient_id == g.user_id,
                    Notification.template == "grievance_update",
                )
            )
        ).all()
        assert sorted(r.payload["status"] for r in rows) == ["acknowledged", "resolved"]
        assert all(r.channel == "in_app" and "Rao" not in str(r.payload) for r in rows)

    async def test_a_stranger_has_nobody_to_tell_so_nothing_is_queued(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        g, ops = await self._one(client, db)
        before = await db.scalar(select(func.count()).select_from(Notification))
        await client.post(f"/ops/grievances/{g.id}/acknowledge", headers=ops)
        assert await db.scalar(select(func.count()).select_from(Notification)) == before

    async def test_an_unknown_id_is_a_404(self, client: AsyncClient, db: AsyncSession) -> None:
        ops = await _operator(client, db)
        assert (
            await client.post(f"/ops/grievances/{uuid.uuid4()}/acknowledge", headers=ops)
        ).status_code == 404


class TestRetentionAndTheRightsOfTheSender:
    async def test_a_closed_grievance_goes_after_its_retention_and_an_open_one_never(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        old = datetime.now(UTC) - timedelta(days=400)
        rows = []
        for status_, resolved in (
            ("resolved", old),
            ("dismissed", old),
            ("resolved", datetime.now(UTC) - timedelta(days=30)),
            ("open", None),
        ):
            g = Grievance(
                reference=f"GRV-{uuid.uuid4().hex[:6].upper()}",
                kind="contact",
                body=GOOD,
                reply_to="a@b.example",
                status=status_,
                resolved_at=resolved,
                created_at=old,
            )
            db.add(g)
            rows.append(g)
        await db.commit()
        removed = await purge_expired(db, retention_days=365)
        assert removed == 2
        left = {g.reference for g in (await db.scalars(select(Grievance))).all()}
        assert rows[0].reference not in left and rows[1].reference not in left
        assert rows[2].reference in left and rows[3].reference in left, "recent and open stay"

    async def test_my_messages_are_mine_alone(self, client: AsyncClient) -> None:
        a, _ = await _signed_in(client)
        b, _ = await _signed_in(client)
        ref = (await client.post(PATH, json={"kind": "contact", "body": GOOD}, headers=a)).json()[
            "reference"
        ]
        assert [m["reference"] for m in (await client.get("/me/grievances", headers=a)).json()] == [
            ref
        ]
        assert (await client.get("/me/grievances", headers=b)).json() == []
        assert (await client.get("/me/grievances")).status_code == 401

    async def test_the_export_shows_them_without_the_operators_note_and_erasure_removes_them(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        sender, _ = await _signed_in(client)
        ref = (
            await client.post(PATH, json={"kind": "grievance", "body": GOOD}, headers=sender)
        ).json()["reference"]
        g = await db.scalar(select(Grievance).where(Grievance.reference == ref))
        ops = await _operator(client, db)
        await client.post(
            f"/ops/grievances/{g.id}/resolve", headers=ops, json={"note": "Internal evidence note."}
        )

        export = (await client.get("/me/account/export", headers=sender)).json()
        mine = export["grievances_raised"]
        assert [m["reference"] for m in mine] == [ref] and mine[0]["message"] == GOOD
        assert "Internal evidence" not in str(export)

        assert (await client.delete("/me/account", headers=sender)).status_code in (200, 204)
        assert await db.scalar(select(Grievance).where(Grievance.reference == ref)) is None
