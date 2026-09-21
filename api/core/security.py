"""Tokens, one-time passcodes and the current-user dependency (ADR-009, ADR-032).

Design notes worth keeping in mind:

* Access tokens are stateless and short lived. Refresh tokens are stateful — a
  record in Redis — so that logout and rotation genuinely revoke, which a purely
  stateless scheme cannot do.
* OTP codes are stored **hashed**. Redis is a plausible read target for an
  attacker, and a plaintext code there is a working credential.
* Everything is keyed off the user's UUID, never the phone number, so a phone
  change does not orphan a session.
"""

import hashlib
import hmac
import secrets
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.cache import get_redis
from api.core.config import get_settings
from api.core.database import get_db_session

if TYPE_CHECKING:  # imported for typing only; a runtime import would cycle
    from api.modules.identity.models import User

TokenType = Literal["access", "refresh"]

_T = TypeVar("_T")


log = structlog.get_logger("iism.auth")


def _aw(value: "Awaitable[_T] | _T") -> "Awaitable[_T]":
    """redis-py shares one signature between its sync and async clients, so
    every call types as `Awaitable[T] | T`. The client here is always async."""
    return cast("Awaitable[_T]", value)


_REFRESH_KEY = "auth:refresh:{jti}"
_USER_REFRESH_SET = "auth:refresh:user:{user_id}"
# The channel is part of every OTP key. Without it a phone and an email that
# happen to normalise to the same string would share one code, one attempt
# counter and one request budget -- and a code issued for one could be spent on
# the other.
_OTP_KEY = "auth:otp:{channel}:{identifier}"
_OTP_ATTEMPTS_KEY = "auth:otp:attempts:{channel}:{identifier}"
_OTP_RATE_KEY = "auth:otp:rate:{channel}:{identifier}"

# How a one-time code reaches its owner. The OTP machinery itself is
# credential-blind (ADR-032: both login paths converge on one token path); only
# delivery differs, and that lives behind an adapter.
Channel = Literal["sms", "email"]

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


# ------------------------------------------------------------------- hashing


def hash_secret(value: str) -> str:
    """Keyed hash for short-lived secrets (OTP codes, refresh identifiers).

    HMAC with the app secret rather than a bare digest, so a leaked Redis dump
    is not itself sufficient to forge a value.
    """
    settings = get_settings()
    return hmac.new(settings.jwt_secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def verify_secret(value: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_secret(value), hashed)


def generate_otp() -> str:
    n = get_settings().otp_length
    return "".join(secrets.choice("0123456789") for _ in range(n))


# -------------------------------------------------------------------- tokens


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if payload.get("type") != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    return payload


async def issue_token_pair(user_id: uuid.UUID) -> TokenPair:
    settings = get_settings()
    now = datetime.now(UTC)
    access_ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    refresh_ttl = timedelta(days=settings.refresh_token_ttl_days)

    access = _encode(
        {
            "sub": str(user_id),
            "type": "access",
            "iat": now,
            "exp": now + access_ttl,
        }
    )

    jti = secrets.token_urlsafe(24)
    refresh = _encode(
        {
            "sub": str(user_id),
            "type": "refresh",
            "jti": jti,
            "iat": now,
            "exp": now + refresh_ttl,
        }
    )

    # Tracked so it can be revoked; the set lets us log out every session.
    redis = get_redis()
    seconds = int(refresh_ttl.total_seconds())
    await redis.set(_REFRESH_KEY.format(jti=jti), str(user_id), ex=seconds)
    await _aw(redis.sadd(_USER_REFRESH_SET.format(user_id=user_id), jti))
    await redis.expire(_USER_REFRESH_SET.format(user_id=user_id), seconds)

    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=int(access_ttl.total_seconds()),
    )


async def rotate_refresh_token(refresh_token: str) -> TokenPair:
    """Exchange a refresh token for a new pair, revoking the one presented.

    Rotation matters: without it a stolen refresh token stays valid for its full
    lifetime alongside the legitimate one.
    """
    payload = decode_token(refresh_token, "refresh")
    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")

    redis = get_redis()
    stored = await redis.get(_REFRESH_KEY.format(jti=jti))
    if stored is None:
        # A refresh token presented twice is a race or a theft, and rotation
        # means the legitimate holder has already exchanged this one. It is
        # the highest-value security signal in the auth path and it was a
        # silent 401. `jti`, not the token: the token is a live credential.
        log.warning("auth.refresh_reuse", user_id=user_id, jti=jti)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token already used or revoked")

    await redis.delete(_REFRESH_KEY.format(jti=jti))
    await _aw(redis.srem(_USER_REFRESH_SET.format(user_id=user_id), jti))
    return await issue_token_pair(uuid.UUID(user_id))


async def revoke_refresh_token(refresh_token: str) -> None:
    """Logout. Never raises on an already-invalid token — the caller's intent is
    to end the session, and reporting failure leaks whether it existed."""
    try:
        payload = decode_token(refresh_token, "refresh")
    except HTTPException:
        return
    jti, user_id = payload.get("jti"), payload.get("sub")
    if jti and user_id:
        redis = get_redis()
        await redis.delete(_REFRESH_KEY.format(jti=jti))
        await _aw(redis.srem(_USER_REFRESH_SET.format(user_id=user_id), jti))


async def revoke_all_for_user(user_id: uuid.UUID) -> int:
    redis = get_redis()
    key = _USER_REFRESH_SET.format(user_id=user_id)
    jtis = await _aw(redis.smembers(key))
    for jti in jtis:
        await redis.delete(_REFRESH_KEY.format(jti=jti))
    await redis.delete(key)
    return len(jtis)


# ----------------------------------------------------------------------- OTP


async def store_otp(channel: Channel, identifier: str, code: str) -> None:
    settings = get_settings()
    redis = get_redis()
    key = _OTP_KEY.format(channel=channel, identifier=identifier)
    await redis.set(key, hash_secret(code), ex=settings.otp_ttl_seconds)
    await redis.delete(_OTP_ATTEMPTS_KEY.format(channel=channel, identifier=identifier))


async def check_otp(channel: Channel, identifier: str, code: str) -> bool:
    """Verify and consume. Counts attempts so a 6-digit code cannot be brute
    forced within its 5-minute window."""
    settings = get_settings()
    redis = get_redis()

    code_key = _OTP_KEY.format(channel=channel, identifier=identifier)
    attempts_key = _OTP_ATTEMPTS_KEY.format(channel=channel, identifier=identifier)

    attempts = await redis.incr(attempts_key)
    if attempts == 1:
        await redis.expire(attempts_key, settings.otp_ttl_seconds)
    if attempts > settings.otp_max_attempts:
        await redis.delete(code_key)
        # `channel` and the attempt count only. The identifier is a phone or an
        # email; the filter would mask it, but a redacted key on every line is
        # noise we would have chosen to create.
        log.warning("auth.otp_attempts_exhausted", channel=channel, attempts=attempts)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Request a new code."
        )

    stored = await redis.get(code_key)
    if stored is None or not verify_secret(code, stored):
        return False

    await redis.delete(code_key)
    await redis.delete(attempts_key)
    return True


async def enforce_otp_rate_limit(channel: Channel, identifier: str) -> None:
    settings = get_settings()
    redis = get_redis()
    key = _OTP_RATE_KEY.format(channel=channel, identifier=identifier)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.otp_request_window_seconds)
    if count > settings.otp_request_limit:
        # An unthrottled OTP endpoint is a denial-of-wallet on the SMS bill.
        # Hitting the ceiling is worth seeing before the invoice is.
        log.warning("auth.otp_rate_limited", channel=channel, count=count)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many codes requested. Try again later.",
        )


# ------------------------------------------------------------ FastAPI wiring


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> "User":
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    payload = decode_token(credentials.credentials, "access")
    from api.modules.identity.models import User  # local import avoids a cycle

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    # Bound here rather than in the middleware, because identity is resolved by
    # a dependency. This works only because `RequestContextMiddleware` is pure
    # ASGI: same task, same context, so the access line written after the
    # handler sees it. The opaque id only -- never phone, email or name.
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> "User | None":
    """The signed-in user if there is one, and `None` otherwise -- never a 401.

    For public routes that must behave differently for someone already signed
    in. `POST /auth/org/register` is the reason it exists: it minted a brand-new
    `User` for any unfamiliar address, so a signed-in candidate who opened
    `/signup/employer` and typed a fresh work email ended up with two separate
    accounts -- the fork ADR-038 exists to prevent.

    An expired or malformed token counts as anonymous rather than as an error,
    because on a public page the honest reading of a stale token is "not signed
    in", and failing a signup form over it would be worse.
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
