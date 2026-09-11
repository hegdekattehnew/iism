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

import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.notifications import get_email_provider, get_notification_provider
from api.core.cache import get_redis
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

# Prepended to the code when someone registers an address that already has an
# account. The HTTP response is identical either way; the difference reaches the
# mailbox, whose owner is the only person entitled to it.
_ALREADY_REGISTERED = (
    "This address already has an IISM account. Entering this code signs you in "
    "and adds the new organisation to it."
)

# A known address asking for a new organisation. Held here until the code comes
# back rather than provisioned at request time: creating it immediately would
# let anyone who knows an address attach an organisation to someone else's
# account. Until Sprint 18 the name was simply discarded, and the person was
# signed into whatever organisation they already had.
_PENDING_ORG_KEY = "auth:pending_org:{address}"


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

    Returns (user, tokens, created). `created` reaches the client on the verify
    response (`SignInOut`) -- it was computed and then dropped by the route until
    Sprint 18, while this docstring claimed a client used it. It is safe there
    and nowhere earlier: the caller has already proved they hold the phone.
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
) -> tuple[User, TokenPair, bool, str | None]:
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

    # "Created" on this path means *first sign-in*: the account row is written
    # at registration, but nobody has proved they hold the mailbox until now.
    created = user.email_verified_at is None
    if created:
        user.email_verified_at = datetime.now(UTC)

    organisation_slug: str | None = None
    pending = await get_redis().getdel(_PENDING_ORG_KEY.format(address=address.lower()))
    if pending:
        # They asked for this organisation at registration and have now proved
        # the address is theirs. One identity, one more membership (ADR-038).
        wanted = json.loads(pending)
        tenant = await provision_organisation(db, user, wanted["name"], wanted["tenant_type"])
        organisation_slug = tenant.slug

    await db.commit()
    await db.refresh(user)
    if organisation_slug is None and created:
        organisation_slug = await _only_organisation_slug(db, user.id)
    return user, await issue_token_pair(user.id), created, organisation_slug


async def _only_organisation_slug(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    """The slug of the user's organisation, if they hold exactly one.

    A brand-new account registered one organisation, so that is where it should
    land. With more than one there is no honest answer, and guessing from an
    unordered list is the defect this replaces.
    """
    slugs = (
        await db.scalars(
            select(Tenant.slug)
            .join(Membership, Membership.tenant_id == Tenant.id)
            .where(Membership.user_id == user_id, Tenant.tenant_type != "personal")
            .limit(2)
        )
    ).all()
    return slugs[0] if len(slugs) == 1 else None


async def has_personal_membership(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Whether this person ever signed up to look for work.

    Only `provision_candidate` creates a personal tenant, and only on a first
    phone sign-in, so an organisation-first account never has one. Everything
    candidate-shaped -- the profile, matches -- is gated on this.
    """
    found = await db.scalar(
        select(Membership.id)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(Membership.user_id == user_id, Tenant.tenant_type == "personal")
        .limit(1)
    )
    return found is not None


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
    the sign-in endpoint. The two paths are then genuinely indistinguishable to
    the caller, and the outcome is better anyway: registering twice signs you in
    rather than failing.

    The organisation it asked for is **held, not discarded** -- see
    `_PENDING_ORG_KEY` -- and created on the existing account once the code
    proves the address is theirs.
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
        await get_redis().set(
            _PENDING_ORG_KEY.format(address=address.lower()),
            json.dumps({"name": name.strip(), "tenant_type": tenant_type}),
            ex=settings.otp_ttl_seconds,
        )
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

    # Case-insensitive for email, as every other email lookup here is. A
    # case-sensitive comparison let `Admin@Clinic.in` walk past a 409 meant to
    # protect `admin@clinic.in`, straight into the unique index.
    match = (
        User.phone == identifier
        if channel == "sms"
        else func.lower(User.email) == identifier.lower()
    )
    holder = await db.scalar(select(User).where(match))
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
