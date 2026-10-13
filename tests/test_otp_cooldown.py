"""A wait between two requests for a code (Sprint 56, BL-14.1).

A one-time code is the only way in, so a code that does not arrive is a lost user, and the person's
next move is to press the button again. The existing budget (5 per identifier per 15 minutes)
stops a flood but not the double tap, and the sign-up form had no way to ask again at all.
These pin the cooldown that every way of asking for a code now shares, what it must *not* do
(spend the budget, replace the code already sent, tell anyone whether an account exists), and
that the forms can count down from the number the server gives them.

The suite runs with the cooldown off (`tests/conftest.py`), as it does the request limiter, so each
class here switches it on.
"""

import asyncio
import uuid
from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.core.config import Settings, get_settings


@pytest.fixture
def cooldown(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("OTP_RESEND_COOLDOWN_SECONDS", "30")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("OTP_RESEND_COOLDOWN_SECONDS")
    get_settings.cache_clear()


def _phone() -> str:
    return "9" + str(uuid.uuid4().int)[:9]


def _email() -> str:
    return f"cooldown-{uuid.uuid4().hex[:12]}@iism-fixtures.co.in"


class TestTheDefaults:
    def test_production_asks_for_a_wait_and_the_suite_does_not(self) -> None:
        assert Settings.model_fields["otp_resend_cooldown_seconds"].default == 30
        assert get_settings().otp_resend_cooldown_seconds == 0


class TestTheWait:
    async def test_a_second_request_inside_the_wait_is_a_429_that_says_how_long(
        self, client: AsyncClient, cooldown: None
    ) -> None:
        phone = _phone()
        first = await client.post("/auth/otp/request", json={"phone": phone})
        assert first.status_code == 200
        assert first.json()["resend_after_seconds"] == 30

        second = await client.post("/auth/otp/request", json={"phone": phone})
        assert second.status_code == 429
        wait = int(second.headers["retry-after"])
        assert 1 <= wait <= 30
        assert str(wait) in second.json()["detail"]

    async def test_it_is_per_identifier_and_per_channel(
        self, client: AsyncClient, cooldown: None
    ) -> None:
        phone, other = _phone(), _phone()
        assert (await client.post("/auth/otp/request", json={"phone": phone})).status_code == 200
        # Another number is not waiting.
        assert (await client.post("/auth/otp/request", json={"phone": other})).status_code == 200
        # An address that merely looks like nothing the phone path holds is its own channel.
        assert (
            await client.post("/auth/email/otp/request", json={"email": _email()})
        ).status_code == 200

    async def test_the_wait_ends(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTP_RESEND_COOLDOWN_SECONDS", "1")
        get_settings.cache_clear()
        try:
            phone = _phone()
            assert (
                await client.post("/auth/otp/request", json={"phone": phone})
            ).status_code == 200
            assert (
                await client.post("/auth/otp/request", json={"phone": phone})
            ).status_code == 429
            await asyncio.sleep(1.3)
            assert (
                await client.post("/auth/otp/request", json={"phone": phone})
            ).status_code == 200
        finally:
            monkeypatch.delenv("OTP_RESEND_COOLDOWN_SECONDS")
            get_settings.cache_clear()

    async def test_a_refused_request_leaves_the_code_already_sent_valid(
        self, client: AsyncClient, cooldown: None
    ) -> None:
        phone = _phone()
        code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
        assert (await client.post("/auth/otp/request", json={"phone": phone})).status_code == 429
        # The person's first message is still the right one: pressing the button too early must
        # not make the code they are about to type wrong.
        verified = await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
        assert verified.status_code == 200, verified.text

    async def test_waiting_does_not_spend_the_budget(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTP_RESEND_COOLDOWN_SECONDS", "1")
        monkeypatch.setenv("OTP_REQUEST_LIMIT", "2")
        get_settings.cache_clear()
        try:
            phone = _phone()
            assert (
                await client.post("/auth/otp/request", json={"phone": phone})
            ).status_code == 200
            # Four presses inside the wait: refused, and none of them counted.
            for _ in range(4):
                assert (
                    await client.post("/auth/otp/request", json={"phone": phone})
                ).status_code == 429
            await asyncio.sleep(1.3)
            assert (
                await client.post("/auth/otp/request", json={"phone": phone})
            ).status_code == 200
        finally:
            monkeypatch.delenv("OTP_RESEND_COOLDOWN_SECONDS")
            monkeypatch.delenv("OTP_REQUEST_LIMIT")
            get_settings.cache_clear()

    async def test_the_answer_is_the_same_for_an_address_with_an_account_and_one_without(
        self, client: AsyncClient, cooldown: None
    ) -> None:
        # Sign up one address, then ask for a code for it and for a stranger: both are 200 with the
        # same fields, and both then wait. The wait must not be an oracle for "this exists".
        known = _email()
        code = (
            await client.post(
                "/auth/org/register",
                json={
                    "email": known,
                    "organisation_name": f"Wait {uuid.uuid4().hex[:6]}",
                    "tenant_type": "employer",
                    "consent_version": CONSENT,
                },
            )
        ).json()
        assert code["resend_after_seconds"] == 30
        stranger = _email()
        a = await client.post("/auth/email/otp/request", json={"email": stranger})
        again_known = await client.post("/auth/email/otp/request", json={"email": known})
        again_stranger = await client.post("/auth/email/otp/request", json={"email": stranger})
        assert a.status_code == 200
        assert again_known.status_code == again_stranger.status_code == 429
        assert (
            again_known.json()["detail"].split()[:6] == again_stranger.json()["detail"].split()[:6]
        )


class TestEveryWayOfAskingForACodeWaits:
    async def test_organisation_registration_waits_too(
        self, client: AsyncClient, cooldown: None
    ) -> None:
        body = {
            "email": _email(),
            "organisation_name": f"Wait {uuid.uuid4().hex[:6]}",
            "tenant_type": "employer",
            "consent_version": CONSENT,
        }
        assert (await client.post("/auth/org/register", json=body)).status_code == 200
        assert (await client.post("/auth/org/register", json=body)).status_code == 429

    async def test_an_organisation_resend_uses_the_sign_in_request_not_a_second_registration(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """What the sign-up form does when the code did not arrive. Registering again for an address
        that now exists would hold a second pending organisation of the same name, and the
        duplicate-name refusal would then fail the person at verification."""
        monkeypatch.setenv("OTP_RESEND_COOLDOWN_SECONDS", "1")
        get_settings.cache_clear()
        try:
            address = _email()
            name = f"Resend {uuid.uuid4().hex[:6]}"
            await client.post(
                "/auth/org/register",
                json={
                    "email": address,
                    "organisation_name": name,
                    "tenant_type": "employer",
                    "consent_version": CONSENT,
                },
            )
            await asyncio.sleep(1.3)
            code = (await client.post("/auth/email/otp/request", json={"email": address})).json()[
                "debug_code"
            ]
            signed_in = await client.post(
                "/auth/email/otp/verify",
                json={"email": address, "code": code, "consent_version": CONSENT},
            )
            assert signed_in.status_code == 200, signed_in.text
            headers = {"authorization": f"Bearer {signed_in.json()['access_token']}"}
            me = (await client.get("/auth/me", headers=headers)).json()
            employers = [m for m in me["memberships"] if m["tenant"]["tenant_type"] == "employer"]
            assert len(employers) == 1
        finally:
            monkeypatch.delenv("OTP_RESEND_COOLDOWN_SECONDS")
            get_settings.cache_clear()

    async def test_asking_for_a_code_to_link_a_credential_waits_too(
        self, client: AsyncClient, cooldown: None
    ) -> None:
        phone = _phone()
        code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
        tokens = (
            await client.post(
                "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
            )
        ).json()
        headers = {"authorization": f"Bearer {tokens['access_token']}"}
        address = _email()
        first = await client.post("/me/credentials/email", json={"email": address}, headers=headers)
        assert first.status_code == 200 and first.json()["resend_after_seconds"] == 30
        second = await client.post(
            "/me/credentials/email", json={"email": address}, headers=headers
        )
        assert second.status_code == 429 and "retry-after" in second.headers
