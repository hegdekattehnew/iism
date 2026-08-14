import re
import secrets
import uuid
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email import get_email_adapter
from app.adapters.google_oauth import get_google_oauth_adapter
from app.config import settings
from app.core.security import (
    consume_oauth_state,
    consume_opaque_token,
    create_oauth_state,
    create_opaque_token,
    get_refresh_token_owner,
    hash_password,
    issue_token_pair,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    verify_password,
)
from app.core.security import decode_token as _decode_token
from app.modules.identity.models import Membership, Tenant, User
from app.modules.identity.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenPair,
)


def _generate_slug(base: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "user"
    return f"{normalized}-{secrets.token_hex(4)}"


async def _create_personal_tenant(db: AsyncSession, user: User) -> Tenant:
    tenant = Tenant(
        name=f"{user.full_name}'s workspace",
        slug=_generate_slug(user.full_name or user.email),
        tenant_type="personal",
    )
    db.add(tenant)
    await db.flush()
    db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
    return tenant


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def _send_verification_email(user: User) -> None:
    token = await create_opaque_token(
        "email_verify", user.id, timedelta(hours=settings.email_verification_token_expire_hours)
    )
    link = f"{settings.app_base_url}/auth/verify-email/confirm?token={token}"
    await get_email_adapter().send(
        user.email, "Verify your email", f"Confirm your email address: {link}"
    )


async def register_user(db: AsyncSession, data: RegisterRequest) -> tuple[User, TokenPair]:
    if await _get_user_by_email(db, data.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush()
    await _create_personal_tenant(db, user)
    await db.commit()
    await db.refresh(user)

    await _send_verification_email(user)
    access_token, refresh_token = await issue_token_pair(user.id)
    return user, TokenPair(access_token=access_token, refresh_token=refresh_token)


async def authenticate_user(db: AsyncSession, data: LoginRequest) -> tuple[User, TokenPair]:
    user = await _get_user_by_email(db, data.email)
    if user is None or user.hashed_password is None or not verify_password(
        data.password, user.hashed_password
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is disabled")

    access_token, refresh_token = await issue_token_pair(user.id)
    return user, TokenPair(access_token=access_token, refresh_token=refresh_token)


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        claims = _decode_token(refresh_token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")

    jti = claims["jti"]
    user_id = uuid.UUID(claims["sub"])
    owner = await get_refresh_token_owner(jti)
    if owner is None or owner != str(user_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token has been revoked")

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    await revoke_refresh_token(jti, user_id)
    access_token, new_refresh_token = await issue_token_pair(user.id)
    return TokenPair(access_token=access_token, refresh_token=new_refresh_token)


async def logout(refresh_token: str) -> None:
    try:
        claims = _decode_token(refresh_token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
    await revoke_refresh_token(claims["jti"], uuid.UUID(claims["sub"]))


async def logout_all(user: User) -> None:
    await revoke_all_refresh_tokens(user.id)


async def request_email_verification(user: User) -> None:
    await _send_verification_email(user)


async def confirm_email_verification(db: AsyncSession, token: str) -> None:
    user_id = await consume_opaque_token("email_verify", token)
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")
    user.is_email_verified = True
    await db.commit()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    user = await _get_user_by_email(db, email)
    if user is None:
        return
    token = await create_opaque_token(
        "password_reset", user.id, timedelta(hours=settings.password_reset_token_expire_hours)
    )
    link = f"{settings.app_base_url}/auth/password-reset/confirm?token={token}"
    await get_email_adapter().send(user.email, "Reset your password", f"Reset link: {link}")


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> None:
    user_id = await consume_opaque_token("password_reset", token)
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")
    user.hashed_password = hash_password(new_password)
    await db.commit()
    await revoke_all_refresh_tokens(user.id)


async def get_google_authorization_url() -> str:
    state = await create_oauth_state()
    return get_google_oauth_adapter().build_authorization_url(state)


async def handle_google_callback(db: AsyncSession, code: str, state: str) -> tuple[User, TokenPair]:
    if not await consume_oauth_state(state):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired OAuth state")

    adapter = get_google_oauth_adapter()
    google_access_token = await adapter.exchange_code_for_access_token(code)
    info = await adapter.fetch_user_info(google_access_token)

    user = await db.scalar(select(User).where(User.google_id == info.google_id))
    if user is None:
        user = await _get_user_by_email(db, info.email)
        if user is not None:
            user.google_id = info.google_id
        else:
            user = User(
                email=info.email,
                full_name=info.full_name,
                google_id=info.google_id,
                is_email_verified=True,
            )
            db.add(user)
            await db.flush()
            await _create_personal_tenant(db, user)
        await db.commit()
        await db.refresh(user)

    access_token, refresh_token = await issue_token_pair(user.id)
    return user, TokenPair(access_token=access_token, refresh_token=refresh_token)
