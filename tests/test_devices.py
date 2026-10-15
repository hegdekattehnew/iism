"""The phones a person has signed in on (Sprint 65, BL-15.6, ADR-075).

A device token is a credential to send to that phone and a fact about a person, so the rules are
about who holds it: one person at a time, only their own can be removed, a bounded number, shown in
their export **without the token**, and erased with the account.
"""

import json
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.notifications import DeviceToken
from api.modules.notifications.devices import MAX_DEVICES
from tests.test_operations import _candidate


def _token() -> str:
    return f"ExponentPushToken[{uuid.uuid4().hex}]"


async def _person(client: AsyncClient) -> tuple[dict[str, str], uuid.UUID]:
    headers = await _candidate(client)
    me = (await client.get("/auth/me", headers=headers)).json()
    return headers, uuid.UUID(me["id"])


async def _register(client: AsyncClient, headers: dict[str, str], token: str, **over: object):
    body = {"token": token, "platform": "android", "locale": "hi", **over}
    return await client.post("/me/devices", json=body, headers=headers)


async def _held(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await db.scalars(select(DeviceToken.token).where(DeviceToken.user_id == user_id))
    return list(rows.all())


class TestRegistering:
    async def test_a_signed_in_person_registers_a_phone(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await _person(client)
        token = _token()
        assert (await _register(client, headers, token)).status_code == 204
        assert await _held(db, uid) == [token]
        row = (await db.scalars(select(DeviceToken).where(DeviceToken.token == token))).one()
        assert (row.platform, row.locale) == ("android", "hi")

    async def test_registering_again_is_one_row_not_two(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await _person(client)
        token = _token()
        await _register(client, headers, token)
        await _register(client, headers, token, platform="ios")
        assert await _held(db, uid) == [token]
        row = (await db.scalars(select(DeviceToken).where(DeviceToken.token == token))).one()
        assert row.platform == "ios"

    async def test_an_anonymous_caller_is_refused(self, client: AsyncClient) -> None:
        response = await client.post("/me/devices", json={"token": _token(), "platform": "android"})
        assert response.status_code == 401

    async def test_a_token_must_be_a_plausible_one(self, client: AsyncClient) -> None:
        headers, _ = await _person(client)
        for bad in ["short", "has a space in it ok", "x" * 600, "tab\tinside-token-1"]:
            assert (await _register(client, headers, bad)).status_code == 422, bad
        assert (await _register(client, headers, _token(), platform="windows")).status_code == 422

    async def test_a_token_belongs_to_one_person_at_a_time(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        """On a shared phone the last person to sign in is the one the next push is for."""
        first, first_id = await _person(client)
        second, second_id = await _person(client)
        token = _token()
        await _register(client, first, token)
        await _register(client, second, token)
        assert await _held(db, first_id) == []
        assert await _held(db, second_id) == [token]
        assert (
            await db.scalar(
                select(func.count()).select_from(DeviceToken).where(DeviceToken.token == token)
            )
        ) == 1

    async def test_a_person_holds_a_bounded_number_and_the_newest_stay(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await _person(client)
        tokens = [_token() for _ in range(MAX_DEVICES + 3)]
        for token in tokens:
            await _register(client, headers, token)
        held = await _held(db, uid)
        assert len(held) == MAX_DEVICES
        assert tokens[-1] in held


class TestUnregistering:
    async def test_it_removes_their_own_phone(self, client: AsyncClient, db: AsyncSession) -> None:
        headers, uid = await _person(client)
        token = _token()
        await _register(client, headers, token)
        response = await client.post(
            "/me/devices/unregister", json={"token": token}, headers=headers
        )
        assert response.status_code == 204
        assert await _held(db, uid) == []

    async def test_it_cannot_remove_somebody_elses_and_says_the_same_thing(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        owner, owner_id = await _person(client)
        stranger, _ = await _person(client)
        token = _token()
        await _register(client, owner, token)
        theirs = await client.post(
            "/me/devices/unregister", json={"token": token}, headers=stranger
        )
        unknown = await client.post(
            "/me/devices/unregister", json={"token": _token()}, headers=stranger
        )
        assert (theirs.status_code, unknown.status_code) == (204, 204)
        assert await _held(db, owner_id) == [token]

    async def test_it_is_idempotent(self, client: AsyncClient) -> None:
        headers, _ = await _person(client)
        body = {"token": _token()}
        for _ in range(2):
            assert (
                await client.post("/me/devices/unregister", json=body, headers=headers)
            ).status_code == 204


class TestWhatThePersonSeesAndWhatIsErased:
    async def test_the_export_lists_the_phone_and_never_the_token(
        self, client: AsyncClient
    ) -> None:
        headers, _ = await _person(client)
        token = _token()
        await _register(client, headers, token)
        exported = (await client.get("/me/account/export", headers=headers)).json()
        assert [d["platform"] for d in exported["devices"]] == ["android"]
        assert set(exported["devices"][0]) == {
            "platform",
            "locale",
            "registered_at",
            "last_seen_at",
        }
        assert token not in json.dumps(exported)

    async def test_an_empty_account_exports_an_empty_list_not_a_missing_key(
        self, client: AsyncClient
    ) -> None:
        headers, _ = await _person(client)
        assert (await client.get("/me/account/export", headers=headers)).json()["devices"] == []

    async def test_erasing_the_account_takes_the_phones(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers, uid = await _person(client)
        await _register(client, headers, _token())
        assert (await client.delete("/me/account", headers=headers)).status_code == 204
        assert await _held(db, uid) == []
