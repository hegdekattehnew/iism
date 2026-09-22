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
from datetime import UTC, datetime, timedelta

import structlog
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
from api.modules.identity.invitations import PENDING_INVITE_KEY
from api.modules.identity.models import Invitation, Membership, Tenant, User

log = structlog.get_logger("iism.identity")

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


def require_current_consent(version: str | None, *, status_code: int) -> None:
    """Refuse unless `version` is the notice currently in force.

    A stale version means the form someone agreed to is not the text in force
    now, and recording it would record consent to something else.
    """
    if version != get_settings().privacy_notice_version:
        raise HTTPException(status_code, "consent_required")


def record_consent(user: User, version: str) -> None:
    user.consent_version = version
    user.consented_at = datetime.now(UTC)


async def provision_candidate(
    db: AsyncSession, phone: str, consent_version: str | None = None
) -> User:
    """A candidate account and its personal tenant, in one go (ADR-010)."""
    user = User(phone=phone, phone_verified_at=datetime.now(UTC))
    if consent_version is not None:
        # The seed provisions demo candidates with no consent to record.
        record_consent(user, consent_version)
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
    db: AsyncSession, phone: str, code: str, consent_version: str | None = None
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
        # This path creates accounts, so it is where consent is recorded. The
        # check runs *after* the code is verified: the caller has proved they
        # hold the phone, so "this number has no account yet" tells them
        # nothing they could not learn from their own messages. Asking earlier
        # would make the request an enumeration oracle (ADR-038). The code is
        # consumed either way; the client asks for consent and a fresh code.
        require_current_consent(consent_version, status_code=status.HTTP_428_PRECONDITION_REQUIRED)
        assert consent_version is not None  # noqa: S101 - narrowed by the check above
        user = await provision_candidate(db, phone, consent_version)
        created = True
    elif user.phone_verified_at is None:
        user.phone_verified_at = datetime.now(UTC)
    if (
        consent_version == get_settings().privacy_notice_version
        and user.consent_version != consent_version
    ):
        # An existing account agreeing through a form that records it -- the
        # only way an account created before Sprint 20 gains a consent record.
        record_consent(user, consent_version)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    await db.commit()
    await db.refresh(user)
    return user, await issue_token_pair(user.id), created


# --------------------------------------------------------------- organisations


async def verify_email_and_sign_in(
    db: AsyncSession, address: str, code: str, consent_version: str | None = None
) -> tuple[User, TokenPair, bool, str | None]:
    """Sign in with an email code.

    **The 401 on an unknown address is load-bearing, and it stays.** This path
    does not create an account merely because somebody held a valid code: a
    candidate signing in by phone is self-service by design, but an
    organisation account carries a tenant and a name that have to be asked for,
    and a blank organisation minted from a code is worse than a refusal.

    There are exactly **two** exceptions, and both are the same mechanism: a
    key written into Redis by an earlier, authenticated-enough act, read here
    with `getdel` so it is consumed once.

    * `_PENDING_ORG_KEY` -- Sprint 18. They registered an organisation against
      an address that already had an account; it is provisioned now that the
      code proves the address is theirs, never at request time, which would let
      anyone who knows an address attach an organisation to somebody else.
    * `PENDING_INVITE_KEY` -- Sprint 25. Somebody with `MEMBER_INVITE` at a real
      organisation offered this address membership. **That** is what makes
      creating the account safe here: it was not the caller's idea, and the
      invitation is a row this product can point at.

    An address with neither key and no account still gets 401. That case is
    tested first, because everything else in this function is written around
    keeping it true.
    """
    if not await check_otp("email", address, code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired code")

    user = await db.scalar(select(User).where(func.lower(User.email) == address.lower()))
    invitation_id = await get_redis().getdel(PENDING_INVITE_KEY.format(address=address.lower()))
    if user is None and invitation_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect or expired code")
    minted = False
    if user is None:
        # An invited stranger. The account is created here and nowhere else on
        # this path, and consent is recorded on it -- forget that and every
        # request the new account makes afterwards is a 428 (Sprint 20).
        require_current_consent(consent_version, status_code=status.HTTP_428_PRECONDITION_REQUIRED)
        assert consent_version is not None  # noqa: S101 - narrowed by the check above
        user = User(email=address.lower(), email_verified_at=datetime.now(UTC))
        record_consent(user, consent_version)
        db.add(user)
        await db.flush()
        minted = True
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    # "Created" on this path means *first sign-in*, which for a registered
    # organisation is not the same moment as the row being written: the account
    # exists from registration, but nobody has proved they hold the mailbox
    # until now. `minted` is tracked separately rather than folded into the
    # check below, because the invited-stranger branch verifies the address in
    # the same breath as creating the row -- so `email_verified_at is None`
    # would read False and send a brand-new account past its own onboarding.
    created = minted or user.email_verified_at is None
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

    if invitation_id is not None:
        accepted = await _accept_pending_invitation(db, user, uuid.UUID(invitation_id))
        # An invitation that expired or was revoked between the mail and the
        # code returns None: the account still exists and they are still signed
        # in, because refusing the sign-in over a stale invitation would strand
        # somebody who now has an account and no way into it.
        organisation_slug = accepted or organisation_slug

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


async def _accept_pending_invitation(
    db: AsyncSession, user: User, invitation_id: uuid.UUID
) -> str | None:
    """Turn the invitation this sign-in was for into a membership.

    Re-checked here rather than trusted from Redis: the key says only which
    invitation was offered, and between the mail arriving and the code coming
    back it may have been revoked or run out. `invitations.accept` is the one
    function that writes a `Membership` from an invitation, so this goes
    through it rather than adding a second writer.
    """
    from api.modules.identity.invitations import accept  # local: see invitations.py

    invitation = await db.get(Invitation, invitation_id)
    if invitation is None or not invitation.is_open(datetime.now(UTC)):
        return None
    await accept(db, invitation=invitation, user=user)
    return invitation.tenant.slug


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


async def _refuse_duplicate_organisation(db: AsyncSession, user: User, name: str) -> None:
    """Refuse a second organisation this person already has under that name.

    **Not a cap on how many organisations one account may hold.** A staffing
    agency, a hospital group with several registered entities and a training
    partner running multiple centres all legitimately need more than one, and
    the only way round a cap would be a second account -- the fork ADR-038
    exists to prevent, and the thing Sprint 25 spent a sprint making
    unnecessary.

    What this refuses is the same organisation twice, which nothing stopped:
    `_unique_tenant_slug` cheerfully produced `apollo-care-2` and the switcher
    then offered two identical-looking rows. Compared on the **slug** rather
    than the raw string, so "Apollo Care" and "apollo care." are one name.
    """
    wanted = slugify(name)[:60].strip("-")
    if not wanted:
        return  # A name that slugifies to nothing cannot collide meaningfully.
    existing = await db.scalars(
        select(Tenant)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == user.id, Tenant.tenant_type != "personal")
    )
    for tenant in existing:
        if slugify(tenant.name)[:60].strip("-") == wanted:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"You already have an organisation called {tenant.name}",
                # The slug, so the client can offer to switch to it rather
                # than leaving somebody to find it themselves.
                headers={"x-existing-organisation": tenant.slug},
            )


async def _within_organisation_cap(db: AsyncSession, user: User) -> None:
    """Refuse an account creating organisations in bulk.

    Counted over a rolling 24 hours rather than a calendar day, so the limit
    cannot be doubled by waiting for midnight -- the same shape as
    `applications` and `interests`, which is the point: this was the only write
    path in the product that could publish a public page with no limit at all.
    """
    limit = get_settings().max_organisations_per_day
    # **Naive, deliberately.** `tenants.created_at` is a bare `TIMESTAMP`, not
    # `timestamptz` -- unlike `course_interests.created_at`, which the sibling
    # cap in `interests/service.py` compares against with an aware value. Pass
    # an aware datetime here and asyncpg refuses the query outright
    # ("can't subtract offset-naive and offset-aware datetimes"), which is how
    # this was found. The column stores UTC; this is the same instant.
    since = (datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None)
    made = await db.scalar(
        select(func.count())
        .select_from(Tenant)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(
            Membership.user_id == user.id,
            Tenant.tenant_type != "personal",
            Tenant.created_at >= since,
        )
    )
    if (made or 0) >= limit:
        log.warning("organisation.daily_cap_reached", limit=limit)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You have created a lot of organisations today. Try again tomorrow.",
            headers={"retry-after": "3600"},
        )


async def provision_organisation(
    db: AsyncSession, user: User, name: str, tenant_type: str
) -> Tenant:
    """Create an organisation owned by an **existing** user.

    Taking the user rather than creating one is what makes the multi-role case
    work: a candidate asked to start hiring gets a second membership, not a
    second account.

    The two guards are here rather than in the route because **three call sites
    reach this function** -- `POST /me/organisations`, the signed-in branch of
    `/auth/org/register`, and the pending-organisation hand-off inside
    `verify_email_and_sign_in`. A check in one handler is a check the other two
    do not make (Sprint 15).
    """
    await _refuse_duplicate_organisation(db, user, name)
    await _within_organisation_cap(db, user)
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
    db: AsyncSession, address: str, name: str, tenant_type: str, consent_version: str
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
    # Before any lookup, so a missing or stale version gets the same answer
    # whether or not the address already has an account.
    require_current_consent(consent_version, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    settings = get_settings()
    await enforce_otp_rate_limit("email", address)

    existing = await db.scalar(select(User).where(func.lower(User.email) == address.lower()))
    if existing is None:
        user = User(email=address)
        record_consent(user, consent_version)
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
