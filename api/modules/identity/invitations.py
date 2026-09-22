"""Bringing somebody else into an organisation, and the rules about who may.

For twenty-four sprints this product modelled organisations and could only ever
put **one person** in one. All three writers of `Membership` hard-coded
`role="owner"`, so `admin` and `member` were fully mapped permission sets that
nothing on earth could reach, and no endpoint anywhere touched the table.

The consequence was not inconvenience, it was data loss. A sole owner deleting
their account took the organisation, its vacancies, its courses and **every
application to them** with it, telling nobody; the 409 in `privacy/service.py`
that should have stopped it needed a second owner to exist, and its instruction
-- "pass ownership to someone else" -- named an act the product could not
perform. This module is what makes that guard reachable.

Three rules live here, and **here only**:

* **Escalation.** An `admin` may invite a `member` and nothing higher; an
  `owner` may invite either. A permission set cannot express a rule about an
  *argument*, so this is a check in `invite()` rather than a fourth permission.
* **The last owner.** Nobody may be removed, demoted or allowed to leave if
  they are the only owner left. One function answers this for all three paths,
  because Sprint 15's finding was that a guard each handler must remember is a
  guard that eventually is not there.
* **Enumeration.** Inviting an address that already has an account and one that
  does not must be **indistinguishable to the caller**. Sprint 12 shipped an
  oracle of exactly this shape -- two responses differing by one field -- and
  the fix then was the fix now: the difference belongs in the mailbox, whose
  owner is the only person entitled to it.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.cache import get_redis
from api.core.security import hash_secret
from api.modules.identity.models import (
    INVITABLE_ROLES,
    INVITE_TTL_DAYS,
    Invitation,
    Membership,
    Tenant,
    User,
)

log = structlog.get_logger("iism.invitations")

# Per organisation, counting only live ones. The applications-cap pattern: the
# per-minute write limiter does not answer somebody patiently seeding a
# hundred addresses, each of which sends a mail carrying this organisation's
# name.
MAX_PENDING_INVITATIONS = 20

# Held between `POST /auth/email/otp/verify` and the account that verify
# creates, exactly as `_PENDING_ORG_KEY` is. Sprint 18 built that hand-off so a
# known address could register an organisation without it being provisioned at
# request time; the same mechanism, unchanged, is what lets an invited stranger
# accept.
PENDING_INVITE_KEY = "auth:pending_invite:{address}"


def _normalise(address: str) -> str:
    return address.strip().lower()


# --------------------------------------------------------------- the two rules


def _may_grant(actor_role: str, role: str) -> bool:
    """Whether somebody holding `actor_role` may hand out `role`.

    An owner may grant either invitable role. An admin may grant `member`
    only -- otherwise `MEMBER_INVITE` would be a route to promoting yourself by
    proxy: invite a second address you control as an admin, and the ceiling on
    your own role has bought nothing.
    """
    if role not in INVITABLE_ROLES:
        return False
    return True if actor_role == "owner" else role == "member"


async def _owner_count(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """How many **owners** this organisation actually has.

    Counts `Membership` rows, never invitations: an invitation is a claim about
    the future, and letting one satisfy this check is how the organisation ends
    up with nobody able to run it -- see the module docstring.
    """
    return (
        await db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.tenant_id == tenant_id, Membership.role == "owner")
        )
    ) or 0


async def _refuse_if_last_owner(db: AsyncSession, membership: Membership) -> None:
    """The one place that answers "would this leave nobody in charge?".

    Called by removal, demotion and leaving. Three handlers asking the question
    three times is three chances to ask it differently.
    """
    if membership.role != "owner":
        return
    if await _owner_count(db, membership.tenant_id) > 1:
        return
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        "This is the organisation's only owner. Make somebody else an owner first.",
    )


# ------------------------------------------------------------------- inviting


async def _membership_of(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> Membership | None:
    return await db.scalar(
        select(Membership).where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
    )


async def invite(
    db: AsyncSession,
    *,
    tenant: Tenant,
    actor: User,
    actor_role: str,
    email: str,
    role: str,
) -> tuple[Invitation, str]:
    """Offer membership. Returns the row and the **plaintext token**, once.

    The token is returned rather than stored: the row keeps only its HMAC, so a
    dumped table is not a set of working invitations. The caller's single job
    with the plaintext is to put it in the mail -- it is never logged, never
    returned in the API response, and cannot be recovered afterwards. Losing it
    means revoking and inviting again, which is the correct trade.
    """
    address = _normalise(email)
    if not _may_grant(actor_role, role):
        # 403 rather than 422: the request is well-formed, and what refuses it
        # is who is asking. The message names the ceiling, because the caller
        # is a member here and their own role is not news to them.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Your role ({actor_role}) cannot invite somebody as {role}",
        )

    now = datetime.now(UTC)

    # Already one of us? A 409 here is safe and is not an oracle: the caller is
    # a member of this organisation and may read its member list anyway, so
    # they could learn this in one more request.
    existing_user = await db.scalar(select(User).where(func.lower(User.email) == address))
    if existing_user is not None:
        held = await _membership_of(db, tenant.id, existing_user.id)
        if held is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "They are already a member of this organisation"
            )

    live = await _open_invitations(db, tenant.id, now)
    if any(i.email == address for i in live):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "There is already an invitation open for that address"
        )
    if len(live) >= MAX_PENDING_INVITATIONS:
        log.warning("invitation.cap_reached", limit=MAX_PENDING_INVITATIONS)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "There are too many invitations open. Revoke some before sending more.",
        )

    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        tenant_id=tenant.id,
        email=address,
        role=role,
        token_hash=hash_secret(token),
        invited_by_user_id=actor.id,
        expires_at=now + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invitation)
    await db.flush()

    # Queued in the same transaction as the invitation, never sent inline
    # (ADR-006): an SMTP timeout must not be able to lose the row. Imported
    # inside the function because `notifications` imports this package for
    # `Tenant`, `User` and now `Invitation` -- a module-level import here is an
    # ImportError at boot, which is what `tests/test_import_order.py` exists to
    # catch. Same fix as `skills` and `marketplace` use for `analytics`.
    from api.modules.notifications import enqueue

    await enqueue(
        db,
        # The address lives on the invitation and is resolved from it at send
        # time, so the outbox keeps its rule: a notification row names a
        # recipient and never holds an address. It also means revoking an
        # invitation stops its mail, which storing the address would not.
        recipient_kind="invitation",
        recipient_id=invitation.id,
        channel="email",
        template="organisation_invitation",
        payload={
            "organisation": tenant.name,
            "role": role,
            # The token reaches the invitee and nobody else. It is in the
            # payload because it *is* the message; `redaction.py` never sees
            # this row, and the outbox is not a log sink.
            "path": f"/invite/{token}",
        },
    )
    return invitation, token


async def _open_invitations(
    db: AsyncSession, tenant_id: uuid.UUID, now: datetime
) -> list[Invitation]:
    rows = await db.scalars(
        select(Invitation).where(
            Invitation.tenant_id == tenant_id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at > now,
        )
    )
    return list(rows.all())


async def list_invitations(db: AsyncSession, tenant_id: uuid.UUID) -> list[Invitation]:
    """Every invitation this organisation has sent, newest first.

    Including spent ones: "did we ever invite her, and what happened?" is the
    question this screen exists to answer, and hiding the answer behind a
    filter makes the screen useless the day somebody needs it.
    """
    rows = await db.scalars(
        select(Invitation)
        .where(Invitation.tenant_id == tenant_id)
        .order_by(Invitation.created_at.desc())
    )
    return list(rows.all())


async def revoke(db: AsyncSession, *, tenant_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation:
    """Withdraw an offer that has not been taken up.

    **Revoking an accepted invitation does not remove the membership.** The
    membership is a separate fact with its own guard; letting this path undo it
    would be a way around `_refuse_if_last_owner`.
    """
    invitation = await db.scalar(
        select(Invitation).where(Invitation.id == invitation_id, Invitation.tenant_id == tenant_id)
    )
    # 404, not 403: another organisation's invitation is not this caller's
    # business to learn the existence of.
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That invitation has already been accepted. Remove the member instead.",
        )
    if invitation.revoked_at is None:
        invitation.revoked_at = datetime.now(UTC)
    await db.commit()
    return invitation


# ------------------------------------------------------------------ accepting


async def invitation_for_token(db: AsyncSession, token: str) -> Invitation:
    """The invitation this token opens, if it is still good for anything.

    **410, not 404, for a spent token.** The two are genuinely different
    answers to somebody who holds a link from their own mailbox: "this was
    real and is finished" is worth saying, and it discloses nothing they did
    not already have in their hand.
    """
    invitation = await db.scalar(
        select(Invitation).where(Invitation.token_hash == hash_secret(token))
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if not invitation.is_open(datetime.now(UTC)):
        raise HTTPException(
            status.HTTP_410_GONE,
            f"That invitation has been {invitation.state(datetime.now(UTC))}",
        )
    return invitation


def mask_address(address: str) -> str:
    """Enough of an address to recognise your own, not enough to learn one.

    `priya@clinic.in` becomes `pr***@clinic.in`. The domain stays because it is
    what makes it recognisable, and a two-character local part is the one case
    where showing nothing is better than showing almost everything.
    """
    local, _, domain = address.partition("@")
    head = local[:2] if len(local) > 3 else local[:1]
    return f"{head}***@{domain}" if domain else "***"


async def claim(db: AsyncSession, token: str) -> tuple[Invitation, int, str | None]:
    """Send a sign-in code to the address this invitation was written to.

    **The caller does not get to name the address.** It comes off the
    invitation, so the only account this can ever create is one for the mailbox
    somebody with `MEMBER_INVITE` actually typed -- and the holder still has to
    read the code out of that mailbox. Letting the caller supply an address
    would turn a forwarded invitation link into a way to mint an account
    anywhere.

    Writes `PENDING_INVITE_KEY`, which is the **only** thing that lets
    `verify_email_and_sign_in` create an account, and is consumed there with
    `getdel`. It is short-lived by construction: the key expires with the code.
    """
    # Imported here rather than at module scope: `service` imports this module
    # for `PENDING_INVITE_KEY`, so the reverse at import time is a cycle.
    from api.modules.identity.service import request_email_otp

    invitation = await invitation_for_token(db, token)
    ttl, debug_code = await request_email_otp(invitation.email)
    await get_redis().set(
        PENDING_INVITE_KEY.format(address=invitation.email),
        str(invitation.id),
        ex=ttl,
    )
    return invitation, ttl, debug_code


async def accept(db: AsyncSession, *, invitation: Invitation, user: User) -> Membership:
    """Turn an open invitation into a membership. Single use, by construction.

    Does not check the caller's address against the invitation's. The token is
    the capability -- it arrived in that mailbox and nowhere else -- and
    requiring the two to match would refuse the ordinary case of somebody whose
    account is under a different address from the one a colleague typed.
    """
    now = datetime.now(UTC)
    held = await _membership_of(db, invitation.tenant_id, user.id)
    if held is None:
        held = Membership(user_id=user.id, tenant_id=invitation.tenant_id, role=invitation.role)
        db.add(held)
    # Already a member: accepting is a no-op on the role rather than a
    # downgrade. An owner clicking an old `member` invitation must not demote
    # themselves, which is also how the last owner would vanish.
    invitation.accepted_at = now
    await db.commit()
    await db.refresh(held)

    # Recorded **here**, not in the route, because there are two ways in: the
    # signed-in caller posting to `/invitations/{token}/accept`, and an invited
    # stranger whose acceptance happens inside `verify_email_and_sign_in`. The
    # first version recorded it in the route only, so half the acceptances in
    # the product were invisible -- and the half that was missing is the one
    # the sprint is actually about. This is the single writer of a `Membership`
    # from an invitation, so it is the one honest place to measure it.
    #
    # After the commit, never inside it: `record()` commits, and a rollback in
    # the middle would take the membership with it.
    from api.modules.analytics import record

    await record(
        db,
        "member_invitation_accepted",
        user_id=user.id,
        # The organisation, never the person: an address is an identity, and
        # `analytics_events` carries none.
        subject_type="tenant",
        subject_id=invitation.tenant_id,
        payload={"role": held.role},
    )
    return held


# ------------------------------------------------------------------- members


async def list_members(db: AsyncSession, tenant_id: uuid.UUID) -> list[tuple[Membership, User]]:
    """Who works here. Owners first, then by when they joined."""
    rows = await db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.tenant_id == tenant_id)
        .order_by(Membership.created_at)
    )
    members = [(m, u) for m, u in rows.all()]
    order = {"owner": 0, "admin": 1, "member": 2}
    return sorted(members, key=lambda pair: order.get(pair[0].role, 3))


async def _member_or_404(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    membership = await _membership_of(db, tenant_id, user_id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a member of this organisation")
    return membership


async def set_role(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> Membership:
    """Change somebody's role. Owner only, and never the last owner's."""
    if role not in ("owner", *INVITABLE_ROLES):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown role")
    membership = await _member_or_404(db, tenant_id, user_id)
    if membership.role == role:
        return membership
    # Promotion to owner is always safe; it is the demotion that can empty the
    # room, so the guard runs on the way *down* only.
    if role != "owner":
        await _refuse_if_last_owner(db, membership)
    membership.role = role
    await db.commit()
    await db.refresh(membership)
    return membership


async def remove_member(db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Take somebody out of the organisation. Their listings stay; they belong
    to the organisation, not to whoever happened to post them."""
    membership = await _member_or_404(db, tenant_id, user_id)
    await _refuse_if_last_owner(db, membership)
    await db.delete(membership)
    await db.commit()


async def leave(db: AsyncSession, *, tenant_id: uuid.UUID, user: User) -> None:
    """Show yourself out. The same guard, because it is the same question."""
    await remove_member(db, tenant_id=tenant_id, user_id=user.id)
