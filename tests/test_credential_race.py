"""Removing the phone and the email at the same moment (Sprint 56, BL-14.2, ADR-066).

"Is another way in left?" is a check followed by a write, so two requests can pass it together: with
the phone and the email both verified, removing each at once would leave an account nobody can open
(and the database's `ck_users_has_identifier` would turn the loser into a 500). The user's row is
locked before the check, so the second request waits for the first and then finds the check false.

Committed rows and a session per request (`tests/concurrency.py`): the suite's `db` fixture is one
connection, so two requests there take turns and the race cannot happen.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import select

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.core.database import get_sessionmaker
from api.modules.identity import service
from api.modules.identity.models import User
from tests.concurrency import real_client


async def test_two_removals_at_once_leave_the_account_one_way_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with real_client() as client:
        phone = "9" + str(uuid.uuid4().int)[:9]
        address = f"race-{uuid.uuid4().hex[:10]}@example.org"
        code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
        tokens = (
            await client.post(
                "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
            )
        ).json()
        headers = {"authorization": f"Bearer {tokens['access_token']}"}
        code = (
            await client.post("/me/credentials/email", headers=headers, json={"email": address})
        ).json()["debug_code"]
        linked = await client.post(
            "/me/credentials/email/verify", headers=headers, json={"email": address, "code": code}
        )
        assert linked.status_code == 200, linked.text

        try:
            # Hold each request open after it has read the row, so both are in flight before
            # either writes: without the row lock both would pass the check.
            original = service._locked

            async def slow(db, user):  # type: ignore[no-untyped-def]
                locked = await original(db, user)
                await asyncio.sleep(0.4)
                return locked

            monkeypatch.setattr(service, "_locked", slow)

            first, second = await asyncio.gather(
                client.delete("/me/credentials/phone", headers=headers),
                client.delete("/me/credentials/email", headers=headers),
            )

            assert sorted([first.status_code, second.status_code]) == [200, 409], (
                first.text,
                second.text,
            )
            async with get_sessionmaker()() as db:
                user = await db.scalar(select(User).where(User.email == address))
                if user is None:
                    user = await db.scalar(select(User).where(User.phone.like(f"%{phone[-10:]}")))
                assert user is not None
                assert user.phone is not None or user.email is not None
        finally:
            monkeypatch.undo()
            # The first removal ended every session, so sign in again to erase the account.
            code = (
                (await client.post("/auth/otp/request", json={"phone": phone}))
                .json()
                .get("debug_code")
            )
            if code:
                signed = (
                    await client.post(
                        "/auth/otp/verify",
                        json={"phone": phone, "code": code, "consent_version": CONSENT},
                    )
                ).json()
                if "access_token" in signed:
                    await client.delete(
                        "/me/account",
                        headers={"authorization": f"Bearer {signed['access_token']}"},
                    )
