"""Identity business logic: passwordless sign-in, linking, and provisioning.

**One identity, many roles** (ADR-038). A person is not an actor type. The same
human can be a candidate looking for work and the hiring manager at the clinic
that employs them, so `User` holds both credentials and `Membership` holds one
role per tenant. Everything here is written so that neither path forks the
account:

* both credentials converge on `issue_token_pair`, which takes only a UUID, so
  nothing downstream knows or cares which was used;
* `provision_organisation` takes an **existing** user, so creating an
  organisation never requires a second account;
* which credential a flow requires is decided here, in the service layer, not
  in route handlers -- the one thing ADR-032 named explicitly.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.notifications import get_email_provider, get_notification_provider
from api.core.config import get_settings
from api.core.security import (
    Channel,
    TokenPair,
    check_otp,
    enforce_otp_rate_limit,
    generate_otp,
    issue_token_pair,
    store_otp,
)
from api.core.text import slugify
from api.modules.identity.models import Membership, Tenant, User

_CODE_MESSAGE = "Your IISM verification code is {code}. It expires in 5 minutes."
_CODE_SUBJECT = "Your IISM verification code"

# Sent instead of a code when someone tries to register an address that already
# has an account. The HTTP response is identical either way, so the difference
# reaches the address owner and nobody else -- which is the point.
# Prepended to the code when someone tries to register an address that already
# has an account. No second organisation is created; they simply sign in.
_ALREADY_REGISTERED = (
    "This address already has an IISM account, so no new organisation was created."
)


def _personal_tenant_slug(user_id_hex: str) -> str:
    return f"personal-{user_id_hex[:12]}"


async def _unique_tenant_slug(db: AsyncSession, name: str) -> str:
    """A readable slug for an organisation, disambiguated only when it must be.

    Two employers may legitimately share a name, and a Hindi-only name
    slugifies to nothing at all, so both cases fall back to something unique
    rather than failing at the unique index.
    """
    base = slugify(name)[:60].strip("-") or "org"
    taken = set((await db.scalars(select(Tenant.slug).where(Tenant.slug.like(f"{base}%")))).all())
    if base not in taken:
        return base
    for n in range(2, 100):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    # Vanishingly unlikely, and still better than an IntegrityError at commit.
    return f"{base}-{datetime.now(UTC).timestamp():.0f}"


# --------------------------------------------------------------- sending codes


async def request_otp(phone: str) -> tuple[int, str | None]:
    """Generate, store and send a one-time passcode to a phone.

    No account is created here, and the response is identical whether or not the
    number is known — otherwise this endpoint becomes a way to enumerate which
    phone numbers have accounts.
    """
    settings = get_settings()
    await enforce_otp_rate_limit("sms", phone)

    code = generate_otp()
    await store_otp("sms", phone, code)

    await get_notification_provider().send_sms(phone, _CODE_MESSAGE.format(code=code))
    return settings.otp_ttl_seconds, code if settings.expose_otp else None


async def request_email_otp(address: str) -> tuple[int, str | None]:
    """The same flow for an email address. Same enumeration rule."""
    settings = get_settings()
    await enforce_otp_rate_limit("email", address)

    code = generate_otp()
    await store_otp("email", address, code)

    await get_email_provider().send_email(address, _CODE_SUBJECT, _CODE_MESSAGE.format(code=code))
    return settings.otp_ttl_seconds, code if settings.expose_otp else None


# ------------------------------------------------------------------ candidates


async def provision_candidate(db: AsyncSession, phone: str) -> User:
    """A candidate account and its personal tenant, in one go (ADR-010)."""
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
    if not await check_otp("sms", phone, code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired code")

    user = await db.scalar(select(User).where(User.phone == phone))
    created = False
    if user is None:
        user = await provision_candidate(db, phone)
        created = True
    elif user.phone_verified_at is None:
        user.phone_verified_at = datetime.now(UTC)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    await db.commit()
    await db.refresh(user)
    return user, await issue_token_pair(user.id), created


# --------------------------------------------------------------- organisations


async def verify_email_and_sign_in(
    db: AsyncSession, address: str, code: str
) -> tuple[User, TokenPair, bool]:
    """Sign in with an email code.

    Unlike the phone path this does **not** create an account on first success.
    A candidate signing in by phone is self-service by design; an organisation
    account carries a tenant and a name, which has to be asked for. An unknown
    address that somehow held a valid code gets 401, not a blank organisation.
    """
    if not await check_otp("email", address, code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired code")

    user = await db.scalar(select(User).where(func.lower(User.email) == address.lower()))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired code")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(user)
    return user, await issue_token_pair(user.id), False


async def provision_organisation(
    db: AsyncSession, user: User, name: str, tenant_type: str
) -> Tenant:
    """Create an organisation owned by an **existing** user.

    Taking the user rather than creating one is what makes the multi-role case
    work: a candidate asked to start hiring gets a second membership, not a
    second account.
    """
    tenant = Tenant(
        slug=await _unique_tenant_slug(db, name),
        name=name.strip(),
        tenant_type=tenant_type,
    )
    db.add(tenant)
    await db.flush()

    db.add(Membership(user_id=user.id, tenant_id=tenant.id, role="owner"))
    await db.flush()
    return tenant


async def register_organisation(
    db: AsyncSession, address: str, name: str, tenant_type: str
) -> tuple[int, str | None]:
    """Cold registration: an email address that may or may not already exist.

    **This must not become an enumeration oracle**, and getting that right takes
    more than returning the same status code. An earlier version sent a "you
    already have an account" note instead of a code for a known address, which
    made the two responses differ by one field the moment `expose_otp` was on --
    a prober could read the difference straight off the response.

    So a known address gets a **real sign-in code**, exactly as if it had used
    the sign-in endpoint, and no second organisation is created. The two paths
    are then genuinely indistinguishable to the caller, and the outcome is
    better anyway: registering twice signs you in rather than failing.
    """
    settings = get_settings()
    await enforce_otp_rate_limit("email", address)

    existing = await db.scalar(select(User).where(func.lower(User.email) == address.lower()))
    if existing is None:
        user = User(email=address)
        db.add(user)
        await db.flush()
        await provision_organisation(db, user, name, tenant_type)
        await db.commit()
        body = _CODE_MESSAGE
    else:
        # The address owner learns what happened; the caller learns nothing.
        body = _ALREADY_REGISTERED + " " + _CODE_MESSAGE

    code = generate_otp()
    await store_otp("email", address, code)
    await get_email_provider().send_email(address, _CODE_SUBJECT, body.format(code=code))
    return settings.otp_ttl_seconds, code if settings.expose_otp else None


# ----------------------------------------------------------- linking a second
# credential to an account that already exists


async def request_link_code(channel: Channel, identifier: str) -> tuple[int, str | None]:
    """Send a code to an identifier the signed-in user wants to add.

    Takes no user on purpose: nothing about the account matters until the code
    comes back, and passing one would imply an association that does not yet
    exist.

    Nothing is written until it is verified: an unverified identifier on an
    account is indistinguishable from a verified one at a glance, which is how
    account-takeover-by-typo happens.
    """
    settings = get_settings()
    await enforce_otp_rate_limit(channel, identifier)

    code = generate_otp()
    await store_otp(channel, identifier, code)

    if channel == "sms":
        await get_notification_provider().send_sms(identifier, _CODE_MESSAGE.format(code=code))
    else:
        await get_email_provider().send_email(
            identifier, _CODE_SUBJECT, _CODE_MESSAGE.format(code=code)
        )
    return settings.otp_ttl_seconds, code if settings.expose_otp else None


async def confirm_link(
    db: AsyncSession, user: User, channel: Channel, identifier: str, code: str
) -> User:
    """Attach a verified identifier to the signed-in account.

    Refuses if another account already holds it. Merging two accounts is a real
    operation with real consequences for profiles and memberships, and it is not
    something a login form should perform silently.
    """
    if not await check_otp(channel, identifier, code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired code")

    column = User.phone if channel == "sms" else User.email
    holder = await db.scalar(select(User).where(column == identifier))
    if holder is not None and holder.id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already linked to another account")

    now = datetime.now(UTC)
    if channel == "sms":
        user.phone, user.phone_verified_at = identifier, now
    else:
        user.email, user.email_verified_at = identifier, now

    await db.commit()
    await db.refresh(user)
    return user


async def update_preferred_locale(db: AsyncSession, user: User, locale: str) -> User:
    user.preferred_locale = locale if locale in ("en", "hi") else "en"
    await db.commit()
    await db.refresh(user)
    return user
