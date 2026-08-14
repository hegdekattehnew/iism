import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import get_redis
from app.core.database import get_db_session
from app.modules.identity.models import ServiceAccount, User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(password, hashed_password)


def _encode_token(user_id: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> tuple[str, str]:
    jti = secrets.token_urlsafe(16)
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": now + expires_delta,
    }
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def create_access_token(user_id: uuid.UUID) -> str:
    token, _ = _encode_token(
        user_id, "access", timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    return token


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


async def create_refresh_token(user_id: uuid.UUID) -> str:
    expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)
    token, jti = _encode_token(user_id, "refresh", expires_delta)
    redis = get_redis()
    ttl_seconds = int(expires_delta.total_seconds())
    async with redis.pipeline() as pipe:
        await pipe.set(f"refresh:{jti}", str(user_id), ex=ttl_seconds)
        await pipe.sadd(f"user_refresh_tokens:{user_id}", jti)
        await pipe.execute()
    return token


async def get_refresh_token_owner(jti: str) -> str | None:
    redis = get_redis()
    return await redis.get(f"refresh:{jti}")


async def revoke_refresh_token(jti: str, user_id: uuid.UUID) -> None:
    redis = get_redis()
    async with redis.pipeline() as pipe:
        await pipe.delete(f"refresh:{jti}")
        await pipe.srem(f"user_refresh_tokens:{user_id}", jti)
        await pipe.execute()


async def revoke_all_refresh_tokens(user_id: uuid.UUID) -> None:
    redis = get_redis()
    key = f"user_refresh_tokens:{user_id}"
    jtis = await redis.smembers(key)
    if jtis:
        await redis.delete(*(f"refresh:{jti}" for jti in jtis))
    await redis.delete(key)


async def issue_token_pair(user_id: uuid.UUID) -> tuple[str, str]:
    access_token = create_access_token(user_id)
    refresh_token = await create_refresh_token(user_id)
    return access_token, refresh_token


async def create_opaque_token(prefix: str, user_id: uuid.UUID, expires_in: timedelta) -> str:
    token = secrets.token_urlsafe(32)
    redis = get_redis()
    await redis.set(f"{prefix}:{token}", str(user_id), ex=int(expires_in.total_seconds()))
    return token


async def consume_opaque_token(prefix: str, token: str) -> uuid.UUID | None:
    redis = get_redis()
    key = f"{prefix}:{token}"
    user_id = await redis.get(key)
    if user_id is None:
        return None
    await redis.delete(key)
    return uuid.UUID(user_id)


async def create_oauth_state() -> str:
    state = secrets.token_urlsafe(24)
    redis = get_redis()
    await redis.set(f"oauth_state:{state}", "1", ex=300)
    return state


async def consume_oauth_state(state: str) -> bool:
    redis = get_redis()
    key = f"oauth_state:{state}"
    if await redis.get(key) is None:
        return False
    await redis.delete(key)
    return True


_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        claims = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if claims.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def generate_api_key() -> str:
    return f"sk_live_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


async def get_service_account(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db_session),
) -> ServiceAccount:
    if x_api_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing API key")
    service_account = await db.scalar(
        select(ServiceAccount).where(ServiceAccount.hashed_key == hash_api_key(x_api_key))
    )
    if service_account is None or not service_account.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return service_account
