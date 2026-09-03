"""Identity business logic: passwordless sign-in and account provisioning."""

import re
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.notifications import get_notification_provider
from api.core.config import get_settings
from api.core.security import (
    TokenPair,
    check_otp,
    enforce_otp_rate_limit,
    generate_otp,
    issue_token_pair,
    store_otp,
)
from api.modules.identity.models import Membership, Tenant, User

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")


def _personal_tenant_slug(user_id_hex: str) -> str:
    return f"personal-{user_id_hex[:12]}"


async def request_otp(phone: str) -> tuple[int, str | None]:
    """Generate, store and send a one-time passcode.

    No account is created here, and the response is identical whether or not the
    number is known — otherwise this endpoint becomes a way to enumerate which
    phone numbers have accounts.
    """
    settings = get_settings()
    await enforce_otp_rate_limit(phone)

    code = generate_otp()
    await store_otp(phone, code)

    provider = get_notification_provider()
    await provider.send_sms(
        phone, f"Your IISM verification code is {code}. It expires in 5 minutes."
    )

    return settings.otp_ttl_seconds, code if settings.expose_otp else None


async def _provision_user(db: AsyncSession, phone: str) -> User:
    """Create the user and their personal tenant in one go (ADR-010)."""
    user = User(phone=phone, phone_verified_at=datetime.now(UTC))
    db.add(user)
    await db.flush()

    tenant = Tenant(
        slug=_personal_tenant_slug(user.id.hex),
        name="Personal workspace",
        tenant_type="personal",
    )
    db.add(tenant)
    await db.flush()

    db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
    await db.flush()
    return user


async def verify_otp_and_sign_in(
    db: AsyncSession, phone: str, code: str
) -> tuple[User, TokenPair, bool]:
    """Verify the code, creating the account on first successful sign-in.

    Returns (user, tokens, created) — `created` lets the client route a brand new
    user to profile setup rather than straight to a bare profile page.
    """
    if not await check_otp(phone, code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired code")

    user = await db.scalar(select(User).where(User.phone == phone))
    created = False
    if user is None:
        user = await _provision_user(db, phone)
        created = True
    elif user.phone_verified_at is None:
        user.phone_verified_at = datetime.now(UTC)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    await db.commit()
    await db.refresh(user)
    return user, await issue_token_pair(user.id), created


async def update_preferred_locale(db: AsyncSession, user: User, locale: str) -> User:
    user.preferred_locale = locale if locale in ("en", "hi") else "en"
    await db.commit()
    await db.refresh(user)
    return user
