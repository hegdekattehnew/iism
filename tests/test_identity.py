"""Sprint 4: passwordless sign-in, token lifecycle and account provisioning."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.cache import get_redis
from api.modules.identity import Membership, Tenant, User, normalise_phone


def _phone() -> str:
    """Unique per test: OTP state lives in Redis, which the rollback fixture
    does not cover, so tests must not share a number."""
    return "9" + uuid.uuid4().int.__str__()[:9]


@pytest.fixture(autouse=True)
async def _clear_otp_state():
    yield
    redis = get_redis()
    for pattern in ("auth:otp:*", "auth:refresh:*"):
        keys = [k async for k in redis.scan_iter(match=pattern)]
        if keys:
            await redis.delete(*keys)


async def _sign_in(client: AsyncClient, phone: str | None = None) -> tuple[str, str, str]:
    phone = phone or _phone()
    req = await client.post("/auth/otp/request", json={"phone": phone})
    code = req.json()["debug_code"]
    res = await client.post("/auth/otp/verify", json={"phone": phone, "code": code})
    body = res.json()
    return body["access_token"], body["refresh_token"], phone


# ---------------------------------------------------------- phone handling


def test_phone_normalisation_collapses_indian_formats() -> None:
    """The same number written four ways must be one account, not four."""
    forms = ["9876543210", "09876543210", "+91 98765 43210", "919876543210"]
    assert {normalise_phone(f) for f in forms} == {"+919876543210"}


async def test_verify_accepts_a_different_format_than_requested(
    client: AsyncClient,
) -> None:
    phone = _phone()
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    spaced = f"+91 {phone[:5]} {phone[5:]}"
    res = await client.post("/auth/otp/verify", json={"phone": spaced, "code": code})
    assert res.status_code == 200


# -------------------------------------------------------------- OTP issuing


async def test_otp_request_succeeds_for_an_unknown_number(client: AsyncClient) -> None:
    """Must not reveal whether an account exists — otherwise this endpoint
    enumerates registered phone numbers."""
    res = await client.post("/auth/otp/request", json={"phone": _phone()})
    assert res.status_code == 200 and res.json()["sent"] is True


async def test_otp_request_rejects_a_short_number(client: AsyncClient) -> None:
    assert (await client.post("/auth/otp/request", json={"phone": "12345"})).status_code == 422


async def test_wrong_code_is_rejected(client: AsyncClient) -> None:
    phone = _phone()
    await client.post("/auth/otp/request", json={"phone": phone})
    res = await client.post("/auth/otp/verify", json={"phone": phone, "code": "000000"})
    assert res.status_code == 401


async def test_code_cannot_be_replayed(client: AsyncClient) -> None:
    phone = _phone()
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    assert (
        await client.post("/auth/otp/verify", json={"phone": phone, "code": code})
    ).status_code == 200
    assert (
        await client.post("/auth/otp/verify", json={"phone": phone, "code": code})
    ).status_code == 401


async def test_brute_force_is_blocked_after_five_attempts(client: AsyncClient) -> None:
    phone = _phone()
    await client.post("/auth/otp/request", json={"phone": phone})
    codes = [{"phone": phone, "code": "000000"} for _ in range(5)]
    for payload in codes:
        assert (await client.post("/auth/otp/verify", json=payload)).status_code == 401
    assert (await client.post("/auth/otp/verify", json=codes[0])).status_code == 429


async def test_repeated_requests_are_rate_limited(client: AsyncClient) -> None:
    """An unthrottled OTP endpoint is a denial-of-wallet on the SMS bill."""
    phone = _phone()
    for _ in range(5):
        assert (await client.post("/auth/otp/request", json={"phone": phone})).status_code == 200
    assert (await client.post("/auth/otp/request", json={"phone": phone})).status_code == 429


# ------------------------------------------------------------ provisioning


async def test_first_sign_in_creates_user_tenant_and_membership(
    client: AsyncClient, db: AsyncSession
) -> None:
    access, _, phone = await _sign_in(client)
    me = (await client.get("/auth/me", headers={"authorization": f"Bearer {access}"})).json()

    assert me["phone"] == normalise_phone(phone)
    assert me["phone_verified_at"] is not None
    assert [(m["role"], m["tenant"]["tenant_type"]) for m in me["memberships"]] == [
        ("owner", "personal")
    ]


async def test_second_sign_in_reuses_the_same_account(client: AsyncClient) -> None:
    phone = _phone()
    a1, _, _ = await _sign_in(client, phone)
    a2, _, _ = await _sign_in(client, phone)
    id1 = (await client.get("/auth/me", headers={"authorization": f"Bearer {a1}"})).json()["id"]
    id2 = (await client.get("/auth/me", headers={"authorization": f"Bearer {a2}"})).json()["id"]
    assert id1 == id2


async def test_user_row_requires_an_identifier(db: AsyncSession) -> None:
    """A user with neither phone nor email is meaningless; the DB enforces it."""
    from sqlalchemy.exc import IntegrityError

    db.add(User(full_name="Nobody"))
    with pytest.raises(IntegrityError):
        await db.flush()


# ------------------------------------------------------------------ tokens


async def test_me_requires_a_token(client: AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code == 401


async def test_me_rejects_garbage(client: AsyncClient) -> None:
    res = await client.get("/auth/me", headers={"authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401


async def test_refresh_token_is_not_accepted_as_an_access_token(
    client: AsyncClient,
) -> None:
    """Type confusion here would hand a 30-day credential the powers of a
    15-minute one."""
    _, refresh, _ = await _sign_in(client)
    res = await client.get("/auth/me", headers={"authorization": f"Bearer {refresh}"})
    assert res.status_code == 401


async def test_refresh_rotates_and_revokes_the_old_token(client: AsyncClient) -> None:
    _, refresh, _ = await _sign_in(client)
    first = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert first.status_code == 200
    replay = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert replay.status_code == 401


async def test_logout_revokes_the_refresh_token(client: AsyncClient) -> None:
    _, refresh, _ = await _sign_in(client)
    assert (await client.post("/auth/logout", json={"refresh_token": refresh})).status_code == 204
    assert (await client.post("/auth/refresh", json={"refresh_token": refresh})).status_code == 401


async def test_logout_is_idempotent(client: AsyncClient) -> None:
    """Reporting failure on an unknown token would leak whether it existed."""
    _, refresh, _ = await _sign_in(client)
    await client.post("/auth/logout", json={"refresh_token": refresh})
    assert (await client.post("/auth/logout", json={"refresh_token": refresh})).status_code == 204


async def test_logout_all_kills_every_session(client: AsyncClient) -> None:
    phone = _phone()
    access, r1, _ = await _sign_in(client, phone)
    _, r2, _ = await _sign_in(client, phone)

    assert (
        await client.post("/auth/logout-all", headers={"authorization": f"Bearer {access}"})
    ).status_code == 204
    for token in (r1, r2):
        assert (
            await client.post("/auth/refresh", json={"refresh_token": token})
        ).status_code == 401


async def test_otp_is_not_stored_in_plaintext(client: AsyncClient) -> None:
    """Redis is a plausible read target; a plaintext code there is a credential."""
    phone = _phone()
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    stored = await get_redis().get(f"auth:otp:sms:{normalise_phone(phone)}")
    assert stored is not None and stored != code


async def test_personal_tenant_is_unique_per_user(client: AsyncClient, db: AsyncSession) -> None:
    await _sign_in(client)
    await _sign_in(client)
    tenants = list(await db.scalars(select(Tenant).where(Tenant.tenant_type == "personal")))
    memberships = list(await db.scalars(select(Membership)))
    assert len({t.slug for t in tenants}) == len(tenants)
    assert len(memberships) >= 2
