"""Adding, replacing and removing a sign-in credential (Sprint 56, BL-14.2, ADR-066).

A one-time code is the only way in, so the phone number or email it goes to *is* the account. People
change numbers and lose them. Until now a credential could be linked and nothing could take one
away; and linking a second phone silently overwrote the first, with no word to the old address and
no session ended, so a stolen session could swap the number and keep the account.
"""

import uuid
from collections.abc import Iterator

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.identity import service
from api.modules.identity.models import User


def _phone() -> str:
    return "9" + str(uuid.uuid4().int)[:9]


def _email() -> str:
    return f"creds-{uuid.uuid4().hex[:10]}@iism-fixtures.co.in"


class Mailbox:
    """What the email provider was asked to send."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = False

    async def send_email(self, address: str, subject: str, body: str) -> None:
        if self.fail:
            raise RuntimeError("provider down")
        self.sent.append((address, subject, body))

    def notices(self) -> list[tuple[str, str, str]]:
        return [m for m in self.sent if "sign-in details" in m[1] or "साइन-इन" in m[1]]


@pytest.fixture
def mailbox(monkeypatch: pytest.MonkeyPatch) -> Iterator[Mailbox]:
    box = Mailbox()
    monkeypatch.setattr(service, "get_email_provider", lambda: box)
    yield box


class Person:
    def __init__(self, client: AsyncClient, phone: str, tokens: dict) -> None:
        self.client = client
        self.phone = phone
        self.tokens = tokens
        self.email: str | None = None

    @property
    def headers(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.tokens['access_token']}"}

    async def me(self) -> dict:
        return (await self.client.get("/auth/me", headers=self.headers)).json()

    async def code_for(self, channel: str, identifier: str) -> str:
        field = "phone" if channel == "phone" else "email"
        response = await self.client.post(
            f"/me/credentials/{channel}", headers=self.headers, json={field: identifier}
        )
        assert response.status_code == 200, response.text
        return response.json()["debug_code"]

    async def add(self, channel: str, identifier: str) -> Response:
        code = await self.code_for(channel, identifier)
        field = "phone" if channel == "phone" else "email"
        return await self.client.post(
            f"/me/credentials/{channel}/verify",
            headers=self.headers,
            json={field: identifier, "code": code},
        )

    async def replace(self, channel: str, identifier: str, code: str | None = None) -> Response:
        field = "phone" if channel == "phone" else "email"
        code = code or await self.code_for(channel, identifier)
        response = await self.client.post(
            f"/me/credentials/{channel}/replace",
            headers=self.headers,
            json={field: identifier, "code": code},
        )
        if response.status_code == 200:
            self.tokens = response.json()
        return response

    async def remove(self, channel: str) -> Response:
        response = await self.client.delete(f"/me/credentials/{channel}", headers=self.headers)
        if response.status_code == 200:
            self.tokens = response.json()
        return response


async def _person(client: AsyncClient, *, with_email: bool = True) -> Person:
    phone = _phone()
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    tokens = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    person = Person(client, phone, tokens)
    if with_email:
        person.email = _email()
        assert (await person.add("email", person.email)).status_code == 200
    return person


async def _refresh(client: AsyncClient, refresh_token: str) -> Response:
    return await client.post("/auth/refresh", json={"refresh_token": refresh_token})


class TestAddOnlyAdds:
    async def test_a_different_address_on_an_account_that_has_one_is_a_409_that_names_replace(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        other = _email()
        code = await person.code_for("email", other)
        refused = await client.post(
            "/me/credentials/email/verify",
            headers=person.headers,
            json={"email": other, "code": code},
        )
        assert refused.status_code == 409 and "Replace it instead" in refused.json()["detail"]
        assert (await person.me())["email"] == person.email
        # The refusal came before the code was spent: the same code replaces it.
        assert (await person.replace("email", other, code)).status_code == 200

    async def test_verifying_the_address_already_held_is_harmless(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        assert (await person.add("email", person.email or "")).status_code == 200


class TestReplace:
    async def test_a_phone_is_replaced_and_the_account_follows_the_new_number(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        original_id = (await person.me())["id"]
        new_phone = _phone()

        response = await person.replace("phone", new_phone)

        assert response.status_code == 200, response.text
        assert response.json()["user"]["phone"].endswith(new_phone[-10:])
        assert (await person.me())["id"] == original_id  # signed in, as the same account
        # The new number signs in to the same account.
        code = (await client.post("/auth/otp/request", json={"phone": new_phone})).json()[
            "debug_code"
        ]
        signed = (
            await client.post(
                "/auth/otp/verify",
                json={"phone": new_phone, "code": code, "consent_version": CONSENT},
            )
        ).json()
        me = (
            await client.get(
                "/auth/me", headers={"authorization": f"Bearer {signed['access_token']}"}
            )
        ).json()
        assert me["id"] == original_id and signed["created"] is False

    async def test_the_old_number_no_longer_opens_the_account(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        original_id = (await person.me())["id"]
        old = person.phone
        await person.replace("phone", _phone())

        code = (await client.post("/auth/otp/request", json={"phone": old})).json()["debug_code"]
        stranger = (
            await client.post(
                "/auth/otp/verify", json={"phone": old, "code": code, "consent_version": CONSENT}
            )
        ).json()
        me = (
            await client.get(
                "/auth/me", headers={"authorization": f"Bearer {stranger['access_token']}"}
            )
        ).json()
        assert me["id"] != original_id and stranger["created"] is True

    async def test_every_other_session_ends_and_the_caller_keeps_one(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        other_session = person.tokens["refresh_token"]
        # A second device signs in with the same number.
        code = (await client.post("/auth/otp/request", json={"phone": person.phone})).json()[
            "debug_code"
        ]
        second = (
            await client.post(
                "/auth/otp/verify",
                json={"phone": person.phone, "code": code, "consent_version": CONSENT},
            )
        ).json()

        await person.replace("phone", _phone())

        assert (await _refresh(client, other_session)).status_code == 401
        assert (await _refresh(client, second["refresh_token"])).status_code == 401
        assert (await _refresh(client, person.tokens["refresh_token"])).status_code == 200

    async def test_a_changed_phone_tells_the_accounts_email_and_a_changed_email_tells_the_old_one(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        old_email = person.email
        await person.replace("phone", _phone())
        (to, _, body) = mailbox.notices()[-1]
        assert to == old_email and "phone number" in body and "replaced" in body

        before = len(mailbox.notices())
        new_email = _email()
        await person.replace("email", new_email)
        assert len(mailbox.notices()) == before + 1, "an email change sends exactly one notice"
        (to, _, body) = mailbox.notices()[-1]
        assert to == old_email, "the notice goes to the address that was taken away"
        assert new_email not in body, "and does not print the new address in full"
        assert not any(m[0] == new_email for m in mailbox.notices())

    async def test_a_phone_only_person_has_nobody_to_tell_and_the_change_still_happens(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client, with_email=False)
        before = len(mailbox.notices())
        assert (await person.replace("phone", _phone())).status_code == 200
        assert len(mailbox.notices()) == before

    async def test_a_failing_provider_does_not_undo_the_change(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        new_phone = _phone()
        code = await person.code_for("phone", new_phone)
        mailbox.fail = True
        response = await person.replace("phone", new_phone, code)
        assert response.status_code == 200
        assert (await person.me())["phone"].endswith(new_phone[-10:])

    async def test_a_number_that_belongs_to_another_account_is_refused_and_nothing_changes(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        other = await _person(client, with_email=False)
        code = await person.code_for("phone", other.phone)
        refused = await person.replace("phone", other.phone, code)
        assert refused.status_code == 409
        assert (await person.me())["phone"].endswith(person.phone[-10:])
        assert (await _refresh(client, person.tokens["refresh_token"])).status_code == 200

    async def test_a_wrong_code_changes_nothing_and_ends_no_session(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        new_phone = _phone()
        await person.code_for("phone", new_phone)
        refused = await person.replace("phone", new_phone, "000000")
        assert refused.status_code == 401
        assert (await person.me())["phone"].endswith(person.phone[-10:])
        assert (await _refresh(client, person.tokens["refresh_token"])).status_code == 200

    async def test_nothing_to_replace_and_the_same_value_are_409s(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client, with_email=False)
        code = await person.code_for("email", _email())
        nothing = await person.replace("email", _email(), code)
        assert nothing.status_code == 409 and "Add one instead" in nothing.json()["detail"]

        same = await person.replace("phone", person.phone)
        assert same.status_code == 409

    async def test_it_needs_a_session(self, client: AsyncClient) -> None:
        assert (
            await client.post(
                "/me/credentials/phone/replace", json={"phone": _phone(), "code": "123456"}
            )
        ).status_code == 401
        assert (await client.delete("/me/credentials/phone")).status_code == 401


class TestRemove:
    async def test_the_email_is_removed_while_the_phone_remains_and_the_old_address_is_told(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        old_email = person.email
        response = await person.remove("email")
        assert response.status_code == 200
        me = await person.me()
        assert me["email"] is None and me["email_verified_at"] is None
        assert me["phone"].endswith(person.phone[-10:])
        (to, _, body) = mailbox.notices()[-1]
        assert to == old_email and "removed" in body

    async def test_the_phone_is_removed_while_the_email_remains_and_the_email_is_told(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        old_email = person.email
        assert (await person.remove("phone")).status_code == 200
        assert (await person.me())["phone"] is None
        assert mailbox.notices()[-1][0] == old_email

    async def test_removing_ends_every_other_session_and_keeps_the_callers(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        stale = person.tokens["refresh_token"]
        await person.remove("email")
        assert (await _refresh(client, stale)).status_code == 401
        assert (await _refresh(client, person.tokens["refresh_token"])).status_code == 200

    async def test_the_only_credential_cannot_be_removed(
        self, client: AsyncClient, mailbox: Mailbox
    ) -> None:
        person = await _person(client, with_email=False)
        refused = await person.remove("phone")
        assert refused.status_code == 409 and "only verified way" in refused.json()["detail"]
        assert (await person.me())["phone"] is not None
        # And a credential that is not there is a 409, not a 500.
        assert (await person.remove("email")).status_code == 409

    async def test_the_other_credential_must_be_verified_not_merely_typed_in(
        self, client: AsyncClient, db: AsyncSession, mailbox: Mailbox
    ) -> None:
        person = await _person(client)
        user = await db.scalar(select(User).where(User.phone.like(f"%{person.phone[-10:]}")))
        assert user is not None
        user.phone_verified_at = None  # a number typed in, never proven
        await db.commit()
        refused = await person.remove("email")
        assert refused.status_code == 409
        assert (await person.me())["email"] == person.email
