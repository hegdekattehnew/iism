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
  guard that eventually is not there. (Sprint 44) The answer is only true while
  nobody else is changing the answer, so every act that changes who owns an
  organisation first takes `_lock_ownership` -- see its docstring.
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
from sqlalchemy import func, select, update
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


async def _lock_ownership(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Make "who owns this organisation" a thing one transaction at a time decides.

    `_refuse_if_last_owner` counts owners in one statement and the caller writes
    in another. Under READ COMMITTED two owners acting at the same moment each
    count two and each pass: A demotes B while B demotes A, or both leave, and the
    organisation has nobody in charge -- the outcome Sprint 25 exists to prevent,
    reachable until Sprint 44 by two people pressing a button together.

    The lock is on the **tenant row**, as `FOR NO KEY UPDATE`: it queues every
    other act that changes ownership of *this* organisation behind this one, and
    it does not block a membership insert (which takes `FOR KEY SHARE` on the
    tenant through its foreign key), so an invitation being accepted is never
    held up by it. An advisory lock would work too and be invisible in
    `pg_locks` joins; SERIALIZABLE would put a retry loop around the whole app for
    one rare act. Held until the commit, and taken **before** the count, never
    after it.

    Callers taking more than one (account erasure) must do so in ascending id
    order. Nothing else holds two, so that is the only way this can deadlock.
    """
    await db.execute(
        select(Tenant.id).where(Tenant.id == tenant_id).with_for_update(key_share=True)
    )


async def lock_ownership_of(db: AsyncSession, tenant_ids: list[uuid.UUID]) -> None:
    """`_lock_ownership` for several organisations, in the one order that cannot deadlock.

    Account erasure is the only caller that holds more than one: somebody who
    belongs to three organisations erasing themselves asks the last-owner
    question of all three. Ascending id is what makes two such erasures, which
    may name the same organisations in different orders, queue instead of
    waiting on each other.
    """
    for tenant_id in sorted(set(tenant_ids)):
        await _lock_ownership(db, tenant_id)


async def _require_owner_now(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> Membership:
    """Whether this person is **still** an owner, asked after the lock is held.

    The route checked `MEMBER_MANAGE` when the request arrived, from a membership
    read some time ago. Another owner may have demoted them since, and an owner-only
    act must not complete on authority that has been withdrawn. 403, not 404: they
    belonged here a moment ago, so existence is not news to them.
    """
    membership = await _membership_of(db, tenant_id, user_id)
    if membership is None or membership.role != "owner":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are no longer an owner of this organisation"
        )
    return membership


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
    # `populate_existing`: after `_lock_ownership` this is the read that must see
    # what the *other* transaction just committed, not the copy the identity map
    # has held since the request's own permission check.
    return await db.scalar(
        select(Membership)
        .where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
        .execution_options(populate_existing=True)
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

    # An expired invitation is still "live" to `uq_invitations_live`, whose
    # predicate cannot mention the clock, so inviting the same address again
    # hit the unique index and returned a 500. Close the lapsed row first,
    # stamped with the moment it actually lapsed rather than now.
    await db.execute(
        update(Invitation)
        .where(
            Invitation.tenant_id == tenant.id,
            Invitation.email == address,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
            Invitation.expires_at <= now,
        )
        .values(revoked_at=Invitation.expires_at)
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

    # The commit the route used to make. It belongs here: the invitation and
    # the queued mail are one act, and a handler that has to remember to commit
    # is one that eventually does not.
    await db.commit()
    await db.refresh(invitation)
    # After the commit, never inside it -- see `_record_for_tenant`.
    await _record_for_tenant(
        db,
        "member_invited",
        tenant_id=tenant.id,
        actor_user_id=actor.id,
        payload={"role": role},
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


async def list_invitations(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[tuple[Invitation, str | None]]:
    """Every invitation this organisation has sent, newest first.

    Including spent ones: "did we ever invite her, and what happened?" is the
    question this screen exists to answer, and hiding the answer behind a
    filter makes the screen useless the day somebody needs it.
    """
    rows = list(
        (
            await db.scalars(
                select(Invitation)
                .where(Invitation.tenant_id == tenant_id)
                .order_by(Invitation.created_at.desc())
            )
        ).all()
    )

    # Each invitation with the name of whoever sent it. One lookup per distinct
    # inviter rather than one per row: an organisation with twenty invitations
    # usually has two or three people who sent them.
    #
    # Resolved here rather than in the route, because "the name we show for an
    # inviter is their full name, or their address when they have not given
    # one" is a rule about people, not a shape of a response.
    inviter_ids = {i.invited_by_user_id for i in rows if i.invited_by_user_id is not None}
    names: dict[uuid.UUID, str | None] = {}
    for inviter_id in inviter_ids:
        inviter = await db.get(User, inviter_id)
        names[inviter_id] = (inviter.full_name or inviter.email) if inviter else None

    return [
        (i, names.get(i.invited_by_user_id) if i.invited_by_user_id is not None else None)
        for i in rows
    ]


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


async def _record_for_tenant(
    db: AsyncSession,
    name: str,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: dict[str, object] | None = None,
) -> None:
    """Measure a team event, subjected to the **organisation**, never the person.

    **Call this after the business commit, never before.** `record()` commits,
    so a call made while a membership change is still uncommitted would commit
    that change as a side effect -- and a failure inside `record()` would roll
    it back and return silently, because `record()` never raises. Every caller
    here commits first; that ordering is the rule, and it is why these live in
    the service rather than in a route handler that has to remember it.

    Imported inside the function: `analytics` loads its routes, which load
    `marketplace.models`, which load `skills`, so a module-level import here is
    an ImportError at boot -- the cycle `tests/test_import_order.py` catches.
    """
    from api.modules.analytics import record

    await record(
        db,
        name,
        user_id=actor_user_id,
        subject_type="tenant",
        subject_id=tenant_id,
        payload=payload,
    )


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
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> tuple[Membership, User]:
    """Change somebody's role. Owner only, and never the last owner's.

    Returns the colleague alongside the membership, because the screen naming
    the change has to name the person it happened to. The route used to do that
    lookup itself with a bare `db.get(User, ...)` and an `assert` for the case
    this function has already ruled out.
    """
    if role not in ("owner", *INVITABLE_ROLES):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown role")
    await _lock_ownership(db, tenant_id)
    await _require_owner_now(db, tenant_id, actor_user_id)
    membership = await _member_or_404(db, tenant_id, user_id)
    user = await db.get(User, user_id)
    # `_member_or_404` resolved a membership, and `memberships.user_id` is a
    # foreign key, so the row is there.
    assert user is not None  # noqa: S101
    if membership.role == role:
        # A no-op is not an event. Recording one would put a change in the
        # measurement that nobody made.
        return membership, user
    # Promotion to owner is always safe; it is the demotion that can empty the
    # room, so the guard runs on the way *down* only.
    if role != "owner":
        await _refuse_if_last_owner(db, membership)
    membership.role = role
    await db.commit()
    await db.refresh(membership)
    await _record_for_tenant(
        db,
        "member_role_changed",
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        payload={"role": role},
    )
    return membership, user


async def remove_member(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Take somebody out of the organisation. Their listings stay; they belong
    to the organisation, not to whoever happened to post them.

    **Measured here rather than in the route, and that closes a gap.** Two paths
    reach this function -- an owner removing a colleague, and somebody leaving
    of their own accord -- and only the first went through a handler that
    recorded anything, so every departure a person chose for themselves was
    invisible. That is `accept()`'s lesson one table over: the single writer is
    the only honest place to measure. `self` in the payload keeps the two
    distinguishable, the way `job_closed` carries `automatic`.
    """
    await _lock_ownership(db, tenant_id)
    if actor_user_id != user_id:
        # Removing a colleague is an owner's act; leaving is anybody's.
        await _require_owner_now(db, tenant_id, actor_user_id)
    membership = await _member_or_404(db, tenant_id, user_id)
    await _refuse_if_last_owner(db, membership)
    await db.delete(membership)
    await db.commit()
    await _record_for_tenant(
        db,
        "member_removed",
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        payload={"self": actor_user_id == user_id},
    )


async def leave(db: AsyncSession, *, tenant_id: uuid.UUID, user: User) -> None:
    """Show yourself out. The same guard, because it is the same question."""
    await remove_member(db, tenant_id=tenant_id, actor_user_id=user.id, user_id=user.id)


async def transfer_ownership(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    to_user_id: uuid.UUID,
    then: str,
) -> tuple[Membership, User]:
    """Hand an organisation to a colleague, and step down, as **one** act.

    Until Sprint 44 this was two requests -- promote, then leave -- and the
    second could fail on its own, leaving two owners where one meant to go, or
    (when somebody else raced it) none. Here the promotion and the step-down
    commit together or not at all, behind the ownership lock, with the caller's
    authority re-read after it.

    **The target must already be a member.** An invitation cannot carry
    `owner` (`INVITABLE_ROLES`), so somebody outside is reached by inviting
    them as an admin first. Giving the organisation to an address that has not
    yet proved it holds the mailbox is how an organisation ends up owned by a
    typo.

    The new owner is queued an email in the same transaction, **before** the
    commit: if the notice cannot be written, nothing has changed and nobody has
    been made an owner in silence. It names the organisation and links to the
    team page; it holds no address.
    """
    if to_user_id == actor_user_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Choose somebody else to hand the organisation to",
        )
    await _lock_ownership(db, tenant_id)
    actor = await _require_owner_now(db, tenant_id, actor_user_id)
    target = await _member_or_404(db, tenant_id, to_user_id)
    if target.role == "owner":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "They are already an owner. To step down yourself, change your own role.",
        )
    user = await db.get(User, to_user_id)
    # `_member_or_404` resolved a membership, and `memberships.user_id` is a
    # foreign key, so the row is there.
    assert user is not None  # noqa: S101
    tenant = await db.get(Tenant, tenant_id)
    assert tenant is not None  # noqa: S101

    target.role = "owner"
    if then == "leave":
        await db.delete(actor)
    else:
        actor.role = "admin"

    # Inside the function because `notifications` imports this package for
    # `Invitation`; a module-level import here is the cycle `tests/test_import_order.py`
    # exists to catch.
    from api.modules.notifications import enqueue

    await enqueue(
        db,
        recipient_kind="user",
        recipient_id=to_user_id,
        channel="email",
        template="ownership_received",
        payload={"organisation": tenant.name, "path": f"/employer/{tenant.slug}/team"},
    )
    await db.commit()
    await db.refresh(target)
    await _record_for_tenant(
        db,
        "ownership_transferred",
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        payload={"then": then},
    )
    return target, user
