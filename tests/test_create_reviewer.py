"""The script that makes a store reviewer's demonstration account (Sprint 65, ADR-076)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.modules.identity.models import Membership, User
from scripts.create_reviewer import ReviewerError, create_reviewer
from tests.test_operations import _candidate

CODE = "482913"


def _phone() -> str:
    return f"+9190{uuid.uuid4().int % 100000000:08d}"


async def _user(db: AsyncSession, phone: str) -> User | None:
    return await db.scalar(select(User).where(User.phone == phone))


async def test_a_dry_run_writes_nothing(db: AsyncSession) -> None:
    phone = _phone()
    outcome = await create_reviewer(db, phone, apply=False, attest=False)
    assert outcome.created is False
    assert await _user(db, phone) is None


async def test_applying_without_the_attestation_is_refused_and_writes_nothing(
    db: AsyncSession,
) -> None:
    phone = _phone()
    with pytest.raises(ReviewerError, match="--attest"):
        await create_reviewer(db, phone, apply=True, attest=False)
    assert await _user(db, phone) is None


async def test_it_makes_a_plain_candidate_with_the_current_consent(db: AsyncSession) -> None:
    phone = _phone()
    outcome = await create_reviewer(db, phone, apply=True, attest=True)
    user = await _user(db, phone)
    assert outcome.created and user is not None
    assert user.full_name == "Store Reviewer"
    assert user.consent_version == get_settings().privacy_notice_version
    assert user.is_staff is False
    memberships = (await db.scalars(select(Membership).where(Membership.user_id == user.id))).all()
    assert len(memberships) == 1  # the personal workspace and nothing else


async def test_it_never_touches_an_account_that_already_exists(
    client: AsyncClient, db: AsyncSession
) -> None:
    """The line that keeps a real person's number from becoming a reviewer account by a script."""
    headers = await _candidate(client)
    me = (await client.get("/auth/me", headers=headers)).json()
    existing = await db.get(User, uuid.UUID(me["id"]))
    assert existing is not None and existing.phone is not None
    before = existing.full_name
    with pytest.raises(ReviewerError, match="already has an account"):
        await create_reviewer(db, existing.phone, apply=True, attest=True)
    await db.refresh(existing)
    assert existing.full_name == before


async def test_a_number_that_is_not_a_phone_is_refused(db: AsyncSession) -> None:
    with pytest.raises(ReviewerError, match="not an Indian mobile"):
        await create_reviewer(db, "12345", apply=True, attest=True)


async def test_the_account_it_makes_can_sign_in_with_the_reviewer_code(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    phone = _phone()
    await create_reviewer(db, phone, apply=True, attest=True)
    settings = get_settings()
    monkeypatch.setattr(settings, "reviewer_login_enabled", True)
    monkeypatch.setattr(settings, "reviewer_phones", phone)
    monkeypatch.setattr(settings, "reviewer_code", CODE)
    assert (await client.post("/auth/otp/request", json={"phone": phone})).status_code == 200
    response = await client.post(
        "/auth/otp/verify",
        json={"phone": phone, "code": CODE, "consent_version": settings.privacy_notice_version},
    )
    assert response.status_code == 200
    token = {"authorization": f"Bearer {response.json()['access_token']}"}
    assert (await client.get("/auth/me", headers=token)).json()["full_name"] == "Store Reviewer"
