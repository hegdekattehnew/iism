"""Sprint 20's web and API hardening: headers, body size, rate limits, exposure.

Every one of these was absent, and every one fails silently when absent -- a
missing header, an unlimited endpoint and a public schema all return 200.
"""

import json
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.core.config import Settings, get_settings
from api.modules.marketplace.schemas import JobIn

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------ headers


async def test_every_response_carries_the_security_headers(client: AsyncClient) -> None:
    response = await client.get("/skills")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


async def test_personal_responses_are_never_cached(client: AsyncClient) -> None:
    """The service worker's DENY list, one layer down: a shared phone must not
    serve one person's profile to the next from a cache."""
    assert (await client.get("/auth/me")).headers["cache-control"] == "no-store"
    assert "no-store" not in (await client.get("/skills")).headers.get("cache-control", "")


async def test_hsts_is_sent_outside_local_environments(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert "strict-transport-security" not in (await client.get("/skills")).headers

    import api.core.middleware as middleware

    production = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="x" * 40,
        otp_expose_in_response=False,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr(middleware, "get_settings", lambda: production)
    assert "max-age=" in (await client.get("/skills")).headers["strict-transport-security"]


async def test_cors_does_not_grant_credentials(client: AsyncClient) -> None:
    """Authentication is a bearer header; no route uses a cookie. Allowing
    credentials cross-origin granted a permission nothing needed."""
    response = await client.options(
        "/skills",
        headers={
            "origin": get_settings().web_base_url,
            "access-control-request-method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-credentials" not in response.headers


# ---------------------------------------------------------------- body size


async def test_a_declared_oversized_body_is_refused_before_it_is_read(
    client: AsyncClient,
) -> None:
    body = json.dumps({"phone": "9" * 10, "padding": "x" * (300 * 1024)})
    response = await client.post(
        "/auth/otp/request", content=body, headers={"content-type": "application/json"}
    )
    assert response.status_code == 413


async def test_an_undeclared_oversized_body_is_abandoned(client: AsyncClient) -> None:
    """No Content-Length: counted as it arrives. FastAPI reports an abandoned
    body as 400, which is still a refusal and never buffers the rest."""

    async def stream():  # type: ignore[no-untyped-def]
        yield b'{"phone": "9999999999", "padding": "'
        for _ in range(40):
            yield b"x" * (8 * 1024)
        yield b'"}'

    response = await client.post(
        "/auth/otp/request", content=stream(), headers={"content-type": "application/json"}
    )
    assert response.status_code in (400, 413)


def test_listing_descriptions_and_skill_lists_are_bounded() -> None:
    with pytest.raises(ValidationError):
        JobIn.model_validate({"title_en": "Nurse", "description_en": "x" * 10_001})
    skills = [{"skill_slug": f"s-{i}"} for i in range(51)]
    with pytest.raises(ValidationError):
        JobIn.model_validate({"title_en": "Nurse", "skills": skills})


# -------------------------------------------------------------- rate limits


@pytest.fixture
async def limiter(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Switch the limiter on with tiny budgets, and start from an empty count."""
    from api.core.cache import get_redis

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_READS_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_WRITES_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "2")
    get_settings.cache_clear()
    redis = get_redis()
    async for key in redis.scan_iter("ratelimit:*"):
        await redis.delete(key)
    yield
    # Before monkeypatch restores the environment; the next read picks it up.
    get_settings.cache_clear()


@pytest.mark.usefixtures("limiter")
class TestRateLimits:
    async def test_reads_past_the_budget_get_429(self, client: AsyncClient) -> None:
        statuses = [(await client.get("/skills")).status_code for _ in range(4)]
        assert statuses == [200, 200, 200, 429]
        response = await client.get("/skills")
        assert response.headers["retry-after"] == "60"

    async def test_token_refresh_is_limited(self, client: AsyncClient) -> None:
        """It was open: an unlimited refresh endpoint is an unlimited guess at a
        refresh token."""
        statuses = [
            (await client.post("/auth/refresh", json={"refresh_token": "nope"})).status_code
            for _ in range(3)
        ]
        assert statuses[-1] == 429

    async def test_sign_in_attempts_do_not_spend_the_read_budget(self, client: AsyncClient) -> None:
        for _ in range(3):
            await client.post("/auth/refresh", json={"refresh_token": "nope"})
        assert (await client.get("/skills")).status_code == 200

    async def test_health_is_never_limited(self, client: AsyncClient) -> None:
        """A load balancer's health check must not be the thing that takes a
        healthy instance out of rotation."""
        statuses = {(await client.get("/health")).status_code for _ in range(6)}
        assert 429 not in statuses

    async def test_signed_in_callers_are_counted_per_account(self, client: AsyncClient) -> None:
        """Carrier-grade NAT puts many people behind one address. A per-IP
        limit would throttle strangers for each other."""
        phone = "9" + str(uuid.uuid4().int)[:9]
        # Two auth-bucket calls: exactly the budget.
        code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
        token = (
            await client.post(
                "/auth/otp/verify",
                json={"phone": phone, "code": code, "consent_version": CONSENT},
            )
        ).json()["access_token"]
        for _ in range(3):
            await client.get("/skills")  # the anonymous address is now spent
        assert (await client.get("/skills")).status_code == 429
        signed_in = await client.get("/skills", headers={"authorization": f"Bearer {token}"})
        assert signed_in.status_code == 200

    async def test_an_unreachable_limiter_fails_open(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import api.core.cache as cache

        def broken():  # type: ignore[no-untyped-def]
            raise ConnectionError("redis is down")

        monkeypatch.setattr(cache, "get_redis", broken)
        statuses = {(await client.get("/skills")).status_code for _ in range(5)}
        assert statuses == {200}


def test_forwarded_addresses_are_ignored_unless_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Honouring X-Forwarded-For from anyone lets a client pick a fresh identity
    per request. It is trusted only behind a proxy that overwrites it."""
    from api.core.middleware import _limiter_identity

    scope = {"headers": [(b"x-forwarded-for", b"203.0.113.9")], "client": ("10.0.0.1", 1)}
    assert _limiter_identity(scope) == "ip:10.0.0.1"
    monkeypatch.setenv("RATE_LIMIT_TRUST_FORWARDED", "true")
    get_settings.cache_clear()
    try:
        assert _limiter_identity(scope) == "ip:203.0.113.9"
    finally:
        monkeypatch.delenv("RATE_LIMIT_TRUST_FORWARDED")
        get_settings.cache_clear()


def test_a_forged_token_counts_as_anonymous() -> None:
    from api.core.middleware import _limiter_identity

    scope = {"headers": [(b"authorization", b"Bearer forged")], "client": ("10.0.0.2", 1)}
    assert _limiter_identity(scope) == "ip:10.0.0.2"


# ----------------------------------------------------------------- exposure


def _docs_urls(environment: str) -> list[str | None]:
    """Boot a fresh app in a subprocess -- see `test_security_hardening._paths`."""
    env = {**os.environ, "ENVIRONMENT": environment}
    if environment not in ("development", "test", "ci"):
        env["JWT_SECRET_KEY"] = "x" * 40
        env["OTP_EXPOSE_IN_RESPONSE"] = "false"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json;from api.main import app;"
            "print(json.dumps([app.docs_url, app.redoc_url, app.openapi_url]))",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_api_schema_is_not_published_in_production() -> None:
    """A complete map of every route and field, handed to whoever asks."""
    assert _docs_urls("production") == [None, None, None]
    assert _docs_urls("staging") == [None, None, None]


def test_the_api_schema_is_available_locally() -> None:
    """`make gen-api` reads it; the typed client depends on it."""
    assert _docs_urls("development")[2] == "/openapi.json"
