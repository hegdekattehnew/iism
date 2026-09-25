"""The external-system actor's credential (Sprint 33, BL-7.2).

`get_service_account` is alongside `get_current_user`, not layered under it --
these tests call it directly the same way a FastAPI dependency call would,
bypassing the `Depends(...)` wiring, which is fine: those markers are just
default values, not something the function itself requires.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.security import get_service_account, hash_secret
from api.modules.identity.models import ServiceAccount

RAW_KEY = "a-partner-key-that-is-not-guessable"


async def _account(db: AsyncSession, *, revoked: bool = False) -> ServiceAccount:
    account = ServiceAccount(
        name="acme-hr-integration",
        hashed_key=hash_secret(RAW_KEY),
        revoked_at=datetime.now(UTC) if revoked else None,
    )
    db.add(account)
    await db.commit()
    return account


async def test_a_valid_key_resolves_the_account(db: AsyncSession) -> None:
    created = await _account(db)
    resolved = await get_service_account(key=RAW_KEY, db=db)
    assert resolved.id == created.id
    assert resolved.name == "acme-hr-integration"


async def test_a_missing_key_is_401(db: AsyncSession) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_service_account(key=None, db=db)
    assert exc.value.status_code == 401


async def test_an_unknown_key_is_401(db: AsyncSession) -> None:
    await _account(db)
    with pytest.raises(HTTPException) as exc:
        await get_service_account(key="not-the-real-key", db=db)
    assert exc.value.status_code == 401


async def test_a_revoked_key_is_401(db: AsyncSession) -> None:
    """Revoked, not deleted -- the row still exists, but stops working the
    moment `revoked_at` is set."""
    await _account(db, revoked=True)
    with pytest.raises(HTTPException) as exc:
        await get_service_account(key=RAW_KEY, db=db)
    assert exc.value.status_code == 401


async def test_the_raw_key_is_never_stored(db: AsyncSession) -> None:
    account = await _account(db)
    assert account.hashed_key != RAW_KEY
    assert RAW_KEY not in account.hashed_key


class TestThePartnerRoute:
    async def test_no_key_is_401(self, client: AsyncClient) -> None:
        assert (await client.get("/partners/jobs")).status_code == 401

    async def test_a_wrong_key_is_401(self, client: AsyncClient, db: AsyncSession) -> None:
        await _account(db)
        response = await client.get("/partners/jobs", headers={"X-API-Key": "wrong"})
        assert response.status_code == 401

    async def test_a_valid_key_reaches_the_same_data_public_jobs_returns(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        await _account(db)
        via_key = await client.get("/partners/jobs", headers={"X-API-Key": RAW_KEY})
        public = await client.get("/jobs")
        assert via_key.status_code == 200
        assert via_key.json()["total"] == public.json()["total"]

    async def test_a_revoked_key_loses_access(self, client: AsyncClient, db: AsyncSession) -> None:
        await _account(db, revoked=True)
        response = await client.get("/partners/jobs", headers={"X-API-Key": RAW_KEY})
        assert response.status_code == 401
