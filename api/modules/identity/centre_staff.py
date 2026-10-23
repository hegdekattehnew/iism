"""Who runs a training centre (Sprint 96, ADR-102, BL-18.4).

A centre is a child tenant of an organisation that delivers training, and the person who runs it day
to day holds the role `manager` **on the centre's own row** (`Membership(tenant=centre,
role="manager")`): a real membership, so signing in, leaving and erasure work as they do for
everyone, and a real invitation, so the existing mail-and-accept flow brings them in. Nothing about
the organisation is shared with them.

Four rules live here and nowhere else:

* **Only the organisation brings a manager in or takes one out.** The route is the parent's
  (`/org/{org}/centres/{centre}/managers`, `CENTRE_MANAGE`, an admin's or an owner's), and the
  centre is reached through `core.authorization.centre_for`, so a stranger and another
  organisation's owner get the same 404 for a centre that does not exist. A manager cannot invite
  another (they hold no `MEMBER_INVITE`), and the organisation's own team route cannot offer the
  role (`INVITABLE_ROLES` does not hold it).
* **`manager` exists only on a centre.** Nothing in the table stops a `manager` membership on an
  employer; this module is the only writer of one and refuses anything but a training centre.
* **Changing who runs a centre takes the lock the ownership rules take** (`_lock_ownership`, a
  `FOR NO KEY UPDATE` on the centre's row) **before** the cap and the duplicate are counted, or two
  admins inviting at once would each see room for the tenth manager. A membership insert takes only
  `FOR KEY SHARE` on the tenant, so accepting an invitation is never held up by it.
* **A centre needs no manager to be reachable.** The organisation's owners and admins reach it
  anyway, so there is no "last manager" rule: the last one can be removed and the centre is simply
  run from the organisation again.
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.identity.invitations import (
    _lock_ownership,
    _membership_of,
    _open_invitations,
    _record_for_tenant,
    list_invitations,
    offer,
)
from api.modules.identity.models import Invitation, Membership, Tenant, User

# Managers plus open invitations, per centre. A cap that deters a script, not a promise; it is
# counted under the lock so it holds.
MAX_MANAGERS = 10


async def managers_of(db: AsyncSession, centre: Tenant) -> list[tuple[Membership, User]]:
    """The centre's managers, earliest first."""
    rows = await db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.tenant_id == centre.id, Membership.role == "manager")
        .order_by(Membership.created_at)
    )
    return [(m, u) for m, u in rows.all()]


async def invitations_of(db: AsyncSession, centre: Tenant) -> list[tuple[Invitation, str | None]]:
    """Every invitation the centre has had, spent ones included, newest first."""
    return await list_invitations(db, centre.id)


async def _manager_count(db: AsyncSession, centre: Tenant, now: datetime) -> int:
    members = (
        await db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.tenant_id == centre.id, Membership.role == "manager")
        )
    ) or 0
    return members + len(await _open_invitations(db, centre.id, now))


async def invite_manager(
    db: AsyncSession, *, parent: Tenant, centre: Tenant, actor: User, email: str
) -> Invitation:
    """Ask somebody to run this centre. The mail names the centre and the organisation."""
    if centre.closed_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This centre is closed. Reopen it before asking anyone to run it",
        )
    await _lock_ownership(db, centre.id)
    if await _manager_count(db, centre, datetime.now(UTC)) >= MAX_MANAGERS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A centre can have up to {MAX_MANAGERS} managers, counting invitations still open",
        )
    invitation, _token = await offer(
        db,
        tenant=centre,
        actor=actor,
        email=email,
        role="manager",
        template="centre_manager_invitation",
        payload={"organisation": parent.name, "centre": centre.name},
    )
    return invitation


async def revoke_invitation(
    db: AsyncSession, *, parent: Tenant, centre: Tenant, invitation_id: uuid.UUID
) -> Invitation:
    """Withdraw an offer that has not been taken up."""
    from api.modules.identity.invitations import revoke

    await _lock_ownership(db, centre.id)
    return await revoke(db, tenant_id=centre.id, invitation_id=invitation_id)


async def remove_manager(
    db: AsyncSession, *, parent: Tenant, centre: Tenant, actor: User, user_id: uuid.UUID
) -> None:
    """Take somebody out of the centre. The organisation, and the centre's record, are untouched."""
    await _lock_ownership(db, centre.id)
    membership = await _membership_of(db, centre.id, user_id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a manager of this centre")
    await db.delete(membership)
    await db.commit()
    # After the commit, never inside it: `record()` commits.
    await _record_for_tenant(
        db,
        "member_removed",
        tenant_id=centre.id,
        actor_user_id=actor.id,
        payload={"self": False, "role": "manager"},
    )
