"""A way in for the store reviewers (Sprint 65, BL-15.8, ADR-076).

Both stores reject an app their reviewer cannot sign in to, and a code sent to a phone they do not
hold cannot reach them. The exception is small on purpose, so what is pinned is its **edges**: it is
off by default, it covers only the named phones, it opens only a demonstration account, and it does
not weaken the setting that echoes codes. A test that only showed the reviewer getting in would pass
for a switch that let everybody in.
"""

import uuid

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.core.config import Settings, get_settings
from api.modules.identity.models import User
from tests.test_operations import _candidate

CODE = "482913"


def _phone() -> str:
    return f"+9190{uuid.uuid4().int % 100000000:08d}"


@pytest.fixture
def reviewer(monkeypatch: pytest.MonkeyPatch) -> str:
    """The switch on, one named phone. Settings are cached, so the cached object is edited and put
    back: `get_settings` is the one way anything reads them."""
    phone = _phone()
    settings = get_settings()
    values = {
        "reviewer_login_enabled": True,
        "reviewer_phones": f" {phone} , +919000000099",
        "reviewer_code": CODE,
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    return phone


async def _request(client: AsyncClient, phone: str) -> dict[str, object]:
    response = await client.post("/auth/otp/request", json={"phone": phone})
    assert response.status_code == 200, response.text
    return response.json()


async def _verify(client: AsyncClient, phone: str, code: str):
    return await client.post(
        "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
    )


class TestTheNamedPhones:
    async def test_the_configured_code_signs_a_named_reviewer_in(
        self, client: AsyncClient, reviewer: str
    ) -> None:
        await _request(client, reviewer)
        response = await _verify(client, reviewer, CODE)
        assert response.status_code == 200 and response.json()["access_token"]

    async def test_no_sms_is_sent_for_a_reviewer(
        self, client: AsyncClient, reviewer: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sent: list[tuple[str, str]] = []

        class Spy:
            async def send_sms(self, phone: str, message: str) -> None:
                sent.append((phone, message))

        monkeypatch.setattr("api.modules.identity.service.get_notification_provider", lambda: Spy())
        await _request(client, reviewer)
        await _request(client, _phone())
        assert [p for p, _ in sent if p == reviewer] == []
        assert len(sent) == 1

    async def test_the_phone_is_matched_however_it_was_written(
        self, client: AsyncClient, reviewer: str
    ) -> None:
        digits = reviewer[3:]
        await _request(client, digits)
        assert (await _verify(client, digits, CODE)).status_code == 200

    async def test_the_list_may_be_written_in_any_way_a_phone_is(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The owner types the list into an environment variable by hand: `98765 43210`,
        `09876543210` and `+91 98765 43210` are one phone, as at every other sign-in."""
        number = f"90{uuid.uuid4().int % 100000000:08d}"
        settings = get_settings()
        monkeypatch.setattr(settings, "reviewer_login_enabled", True)
        monkeypatch.setattr(settings, "reviewer_phones", f" {number[:5]} {number[5:]} ")
        monkeypatch.setattr(settings, "reviewer_code", CODE)
        await _request(client, f"+91{number}")
        assert (await _verify(client, f"+91{number}", CODE)).status_code == 200

    async def test_the_answer_to_a_request_is_the_same_for_a_reviewer_and_anybody_else(
        self, client: AsyncClient, reviewer: str
    ) -> None:
        """No oracle for who is on the list: the response differs in nothing but the dev code."""
        mine, other = await _request(client, reviewer), await _request(client, _phone())
        assert set(mine) == set(other)
        assert mine["expires_in_seconds"] == other["expires_in_seconds"]

    async def test_the_fixed_code_does_not_open_any_other_phone(
        self, client: AsyncClient, reviewer: str
    ) -> None:
        stranger = _phone()
        await _request(client, stranger)
        assert (await _verify(client, stranger, CODE)).status_code == 401

    async def test_a_wrong_code_for_a_reviewer_is_still_refused_and_still_capped(
        self, client: AsyncClient, reviewer: str
    ) -> None:
        await _request(client, reviewer)
        for _ in range(get_settings().otp_max_attempts):
            assert (await _verify(client, reviewer, "000000")).status_code == 401
        # The cap burns the code: even the right one is refused (429) until a new one is asked for.
        assert (await _verify(client, reviewer, CODE)).status_code == 429


class TestTheSwitch:
    async def test_it_does_nothing_while_off(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        phone = _phone()
        settings = get_settings()
        monkeypatch.setattr(settings, "reviewer_login_enabled", False)
        monkeypatch.setattr(settings, "reviewer_phones", phone)
        monkeypatch.setattr(settings, "reviewer_code", CODE)
        await _request(client, phone)
        assert (await _verify(client, phone, CODE)).status_code == 401

    def test_it_is_off_by_default(self) -> None:
        assert Settings().reviewer_login_enabled is False


class TestWhatItMayOpen:
    async def test_an_operator_is_refused(
        self, client: AsyncClient, db: AsyncSession, reviewer: str
    ) -> None:
        headers = await _candidate(client)
        me = (await client.get("/auth/me", headers=headers)).json()
        user = await db.get(User, uuid.UUID(me["id"]))
        assert user is not None and user.phone is not None
        user.is_staff = True
        user.staff_tier = "admin"
        await db.flush()
        get_settings().reviewer_phones = user.phone
        await _request(client, user.phone)
        response = await _verify(client, user.phone, CODE)
        assert response.status_code == 403
        assert "demonstration" in response.json()["detail"]

    async def test_an_account_that_belongs_to_an_organisation_is_refused(
        self, client: AsyncClient, db: AsyncSession, reviewer: str
    ) -> None:
        """A candidate who also created an organisation holds other people's data."""
        headers = await _candidate(client)
        created = await client.post(
            "/me/organisations",
            json={
                "organisation_name": f"Reviewer Test {uuid.uuid4().hex[:6]}",
                "tenant_type": "employer",
            },
            headers=headers,
        )
        assert created.status_code in (200, 201), created.text
        me = (await client.get("/auth/me", headers=headers)).json()
        user = await db.get(User, uuid.UUID(me["id"]))
        assert user is not None and user.phone is not None
        get_settings().reviewer_phones = user.phone
        await _request(client, user.phone)
        assert (await _verify(client, user.phone, CODE)).status_code == 403

    async def test_an_ordinary_candidate_account_is_allowed(
        self, client: AsyncClient, db: AsyncSession, reviewer: str
    ) -> None:
        headers = await _candidate(client)
        me = (await client.get("/auth/me", headers=headers)).json()
        user = await db.get(User, uuid.UUID(me["id"]))
        assert user is not None and user.phone is not None
        get_settings().reviewer_phones = user.phone
        await _request(client, user.phone)
        assert (await _verify(client, user.phone, CODE)).status_code == 200


class TestStartupValidation:
    """`Settings` refuses an unsafe combination, so a deployment fails to start rather than running
    with a hole. Each case is built from a **valid** set so the one fault is the one tested."""

    GOOD = {
        "environment": "production",
        "jwt_secret_key": "x" * 48,
        "otp_expose_in_response": False,
        "reviewer_login_enabled": True,
        "reviewer_phones": "+919876543210",
        "reviewer_code": "482913",
    }

    def test_the_valid_set_is_valid(self) -> None:
        assert Settings(**self.GOOD).reviewer_login_enabled is True

    @pytest.mark.parametrize(
        ("change", "why"),
        [
            ({"reviewer_phones": ""}, "no phones named"),
            ({"reviewer_phones": "+919876543210,not-a-phone"}, "an entry that is not a phone"),
            (
                {"reviewer_phones": ",".join(f"+91987654321{i}" for i in range(6))},
                "too many phones",
            ),
            ({"reviewer_code": ""}, "no code"),
            ({"reviewer_code": "12345"}, "too short"),
            ({"reviewer_code": "12345a"}, "not digits"),
            ({"reviewer_code": "111111"}, "one digit repeated"),
            ({"reviewer_code": "123456"}, "a straight run up"),
            ({"reviewer_code": "654321"}, "a straight run down"),
            ({"otp_expose_in_response": True}, "echoing codes is still refused in production"),
        ],
    )
    def test_each_unsafe_shape_is_refused(self, change: dict[str, object], why: str) -> None:
        with pytest.raises(ValidationError):
            Settings(**{**self.GOOD, **change})

    def test_a_guessable_code_is_tolerated_only_in_development(self) -> None:
        dev = {**self.GOOD, "environment": "development", "reviewer_code": "123456"}
        assert Settings(**dev).reviewer_login_enabled is True
