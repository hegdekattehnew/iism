import logging
import re
import uuid

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.core.permissions import require_verified_email
from app.modules.identity.models import User


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client: AsyncClient, email: str | None = None, password: str = "correct-horse-1"):
    email = email or _unique_email()
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    return email, password, response


async def test_register_login_me_happy_path(client: AsyncClient):
    email, _, response = await _register(client)
    assert response.status_code == 201
    tokens = response.json()
    assert tokens["token_type"] == "bearer"

    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == email
    assert body["is_email_verified"] is False
    assert len(body["memberships"]) == 1
    assert body["memberships"][0]["role"] == "owner"


async def test_duplicate_email_registration_rejected(client: AsyncClient):
    email, _, response = await _register(client)
    assert response.status_code == 201
    _, _, response2 = await _register(client, email=email)
    assert response2.status_code == 409


async def test_wrong_password_rejected(client: AsyncClient):
    email, _, response = await _register(client)
    assert response.status_code == 201
    login = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert login.status_code == 401


async def test_invalid_access_token_rejected(client: AsyncClient):
    response = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


async def test_no_token_rejected(client: AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_refresh_rotation(client: AsyncClient):
    _, _, response = await _register(client)
    tokens = response.json()

    refreshed = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    reuse = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401


async def test_logout_invalidates_refresh_token(client: AsyncClient):
    _, _, response = await _register(client)
    tokens = response.json()

    logout = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 204

    reuse = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401


async def test_logout_all_invalidates_all_sessions(client: AsyncClient):
    email, password, response = await _register(client)
    tokens_a = response.json()

    login = await client.post("/auth/login", json={"email": email, "password": password})
    tokens_b = login.json()

    logout_all = await client.post(
        "/auth/logout-all",
        headers={"Authorization": f"Bearer {tokens_a['access_token']}"},
    )
    assert logout_all.status_code == 204

    for tokens in (tokens_a, tokens_b):
        reuse = await client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert reuse.status_code == 401


async def test_email_verification_flow(client: AsyncClient, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="iism.email")
    _, _, response = await _register(client)
    tokens = response.json()

    match = re.search(r"token=([\w-]+)", caplog.text)
    assert match is not None
    token = match.group(1)

    confirm = await client.post("/auth/verify-email/confirm", json={"token": token})
    assert confirm.status_code == 204

    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.json()["is_email_verified"] is True

    reuse = await client.post("/auth/verify-email/confirm", json={"token": token})
    assert reuse.status_code == 400


async def test_password_reset_flow(client: AsyncClient, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="iism.email")
    email, password, response = await _register(client)
    tokens = response.json()

    caplog.clear()
    req = await client.post("/auth/password-reset/request", json={"email": email})
    assert req.status_code == 204

    match = re.search(r"token=([\w-]+)", caplog.text)
    assert match is not None
    token = match.group(1)

    new_password = "brand-new-pw-1"
    confirm = await client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": new_password}
    )
    assert confirm.status_code == 204

    reuse = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401

    old_login = await client.post("/auth/login", json={"email": email, "password": password})
    assert old_login.status_code == 401

    new_login = await client.post("/auth/login", json={"email": email, "password": new_password})
    assert new_login.status_code == 200


async def test_password_reset_request_unknown_email_returns_204(client: AsyncClient):
    response = await client.post(
        "/auth/password-reset/request", json={"email": _unique_email()}
    )
    assert response.status_code == 204


async def test_require_verified_email_blocks_unverified_user():
    unverified = User(email=_unique_email(), full_name="X", is_email_verified=False)
    with pytest.raises(HTTPException) as exc_info:
        await require_verified_email(user=unverified)
    assert exc_info.value.status_code == 403

    verified = User(email=_unique_email(), full_name="Y", is_email_verified=True)
    result = await require_verified_email(user=verified)
    assert result is verified
