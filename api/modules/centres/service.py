"""An organisation's training centres (Sprint 95, ADR-102, BL-18.3).

A centre is a **child tenant** of an organisation that delivers training. It is a place with a
name, an address and a district, and it has no members of its own yet: the parent's owners and
admins reach it through the parent's slug (`core.authorization.centre_for`, the one place that
rule is written).

The rules held here, each in one place:

- **Only an organisation that delivers training has centres** (`capability_for`, asked by the
  route's `require`), and no more than `MAX_CENTRES` of them: a cap that deters a script, not a
  promise.
- **A name is unique within its organisation**, compared as a slug so "Pune Centre" and "pune
  centre." are one centre, and a closed centre counts: it is reopened, not duplicated.
- **The place is resolved, never guessed** (`geography.resolve_location`): an unresolvable name is
  kept as written and the centre says so (`place_resolved`).
- **The "address checked" mark attests the address**, so changing the address or the place of a
  checked centre **takes the mark away**, with an event that says why. A mark that outlives the
  thing it checked would be a claim nobody made.
- **Closing is not deleting**: the history stays, a closed centre is off the public page, and it can
  reopen. Closing a centre with open or running batches is refused once batches exist (Sprint 98).
"""

import re
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.slugs import add_with_unique_slug
from api.core.text import slugify
from api.modules.analytics import record
from api.modules.centres.schemas import CentreIn, CentreOut, ManagedCentreOut
from api.modules.geography import resolve_location
from api.modules.identity.models import Tenant, User
from api.modules.operations.models import TenantVerificationEvent

log = structlog.get_logger("iism.centres")

# A cap that deters abuse, not a limit anybody is promised (CLAUDE.md: a check that guards an
# invariant takes a lock; a cap that deters abuse may stay advisory).
MAX_CENTRES = 200


def _name_key(name: str) -> str:
    return slugify(name) or re.sub(r"\s+", " ", name.strip().lower())


def out(centre: Tenant) -> CentreOut:
    return CentreOut(
        slug=centre.slug,
        name=centre.name,
        address=centre.address,
        location_state=centre.location_state,
        location_district=centre.location_district,
        # The district resolves only inside its state, so its id says both halves matched.
        place_resolved=centre.district_id is not None,
        status="closed" if centre.closed_at is not None else "active",
        closed_at=centre.closed_at,
        is_verified=centre.verified_at is not None,
        created_at=centre.created_at,
    )


async def centres_of(db: AsyncSession, parent: Tenant) -> list[Tenant]:
    """Every centre of an organisation, active first, then by name."""
    rows = await db.scalars(
        select(Tenant)
        .where(Tenant.parent_id == parent.id, Tenant.tenant_type == "training_centre")
        .order_by(Tenant.closed_at.is_(None).desc(), func.lower(Tenant.name), Tenant.id)
    )
    return list(rows.all())


async def active_centre_count(db: AsyncSession, parent_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Tenant)
            .where(
                Tenant.parent_id == parent_id,
                Tenant.tenant_type == "training_centre",
                Tenant.closed_at.is_(None),
            )
        )
    ) or 0


async def centre_count(db: AsyncSession, parent_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(Tenant)
            .where(Tenant.parent_id == parent_id, Tenant.tenant_type == "training_centre")
        )
    ) or 0


async def existing_names(db: AsyncSession, parent_id: uuid.UUID) -> dict[str, str]:
    """`name key -> slug` of every centre the organisation already has, closed ones included."""
    rows = await db.execute(
        select(Tenant.name, Tenant.slug).where(
            Tenant.parent_id == parent_id, Tenant.tenant_type == "training_centre"
        )
    )
    return {_name_key(name): slug for name, slug in rows.all()}


async def _unique_slug(db: AsyncSession, text: str) -> str:
    base = slugify(text)[:60].strip("-") or "centre"
    taken = set((await db.scalars(select(Tenant.slug).where(Tenant.slug.like(f"{base}%")))).all())
    if base not in taken:
        return base
    for n in range(2, 100):
        if f"{base}-{n}" not in taken:
            return f"{base}-{n}"
    return f"{base}-{datetime.now(UTC).timestamp():.0f}"


async def lock_delivering_parent(db: AsyncSession, parent_id: uuid.UUID) -> None:
    """Share-lock the organisation and read the flag again under it.

    `capability_for` was asked at the start of the request; turning *delivers training* off takes
    the ownership lock (`FOR NO KEY UPDATE`) and counts the open centres. `FOR SHARE` conflicts with
    it, so a centre created at the same instant either lands before the count (and the owner is
    refused) or waits and finds the flag off (and is refused here): never a centre under an
    organisation that no longer delivers.
    """
    delivers = await db.scalar(
        select(Tenant.delivers_training)
        .where(Tenant.id == parent_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if not delivers:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This organisation does not deliver training"
        )


async def refuse_if_full(db: AsyncSession, parent: Tenant) -> None:
    if await centre_count(db, parent.id) >= MAX_CENTRES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"An organisation can have up to {MAX_CENTRES} centres. Close one that no longer runs, "
            "or write to us if you need more",
        )


async def add_centre(db: AsyncSession, parent: Tenant, data: CentreIn) -> Tenant:
    """Insert one centre and flush. **Does not commit**: single creation commits, a file of them
    commits once. The refusals are here so both paths make them."""
    names = await existing_names(db, parent.id)
    taken = names.get(_name_key(data.name))
    if taken is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This organisation already has a centre called that ({taken})",
            headers={"x-existing-centre": taken},
        )
    located = await resolve_location(db, data.state, data.district)
    return await add_with_unique_slug(
        db,
        Tenant.slug,
        lambda: _unique_slug(db, f"{parent.name} {data.name}"),
        lambda slug: Tenant(
            slug=slug,
            name=data.name,
            tenant_type="training_centre",
            parent_id=parent.id,
            address=data.address,
            location_state=data.state,
            location_district=data.district,
            state_id=located.state_id,
            district_id=located.district_id,
        ),
    )


async def create_centre(db: AsyncSession, parent: Tenant, actor: User, data: CentreIn) -> Tenant:
    await lock_delivering_parent(db, parent.id)
    await refuse_if_full(db, parent)
    centre = await add_centre(db, parent, data)
    await db.commit()
    await db.refresh(centre)
    # After the commit, never inside it: `record()` commits.
    await record(
        db,
        "centre_created",
        user_id=actor.id,
        subject_type="tenant",
        subject_id=parent.id,
        payload={"placed": centre.district_id is not None},
    )
    return centre


def _address_changed(centre: Tenant, data: CentreIn) -> bool:
    def key(value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    return (
        key(centre.address) != key(data.address)
        or key(centre.location_state) != key(data.state)
        or key(centre.location_district) != key(data.district)
    )


async def update_centre(
    db: AsyncSession, parent: Tenant, centre: Tenant, actor: User, data: CentreIn
) -> Tenant:
    """Change a centre's name, address or place; a checked address that changes loses its mark."""
    if _name_key(data.name) != _name_key(centre.name):
        taken = (await existing_names(db, parent.id)).get(_name_key(data.name))
        if taken is not None and taken != centre.slug:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"This organisation already has a centre called that ({taken})",
                headers={"x-existing-centre": taken},
            )
    if centre.verified_at is not None and _address_changed(centre, data):
        db.add(
            TenantVerificationEvent(
                tenant_id=centre.id,
                decision="revoked",
                note="The address changed after it was checked",
                actor_user_id=actor.id,
            )
        )
        centre.verified_at = None
        centre.verified_by = None
        centre.verification_note = None
    located = await resolve_location(db, data.state, data.district)
    centre.name = data.name
    centre.address = data.address
    centre.location_state = data.state
    centre.location_district = data.district
    centre.state_id = located.state_id
    centre.district_id = located.district_id
    await db.commit()
    await db.refresh(centre)
    return centre


async def close_centre(db: AsyncSession, parent: Tenant, centre: Tenant, actor: User) -> Tenant:
    """Close a centre. Batches (Sprint 98) will add their reason here: an open or running batch
    keeps it open, so a class in progress is never stopped from under its learners."""
    if centre.closed_at is not None:
        return centre
    centre.closed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(centre)
    await record(
        db,
        "centre_closed",
        user_id=actor.id,
        subject_type="tenant",
        subject_id=parent.id,
        payload={},
    )
    return centre


async def reopen_centre(db: AsyncSession, centre: Tenant) -> Tenant:
    centre.closed_at = None
    await db.commit()
    await db.refresh(centre)
    return centre


async def managed_centre(db: AsyncSession, tenant: Tenant) -> tuple[Tenant, Tenant]:
    """`(centre, its organisation)` for the centre a manager is acting in.

    The route has already resolved a membership with `MANAGED_CENTRE_*` in this tenant, so this is
    a second statement of the shape (only a training centre has a parent), not the guard.
    """
    parent = await db.get(Tenant, tenant.parent_id) if tenant.parent_id is not None else None
    if tenant.tenant_type != "training_centre" or parent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    return tenant, parent


def managed_out(centre: Tenant, parent: Tenant) -> ManagedCentreOut:
    base = out(centre)
    return ManagedCentreOut(
        **base.model_dump(), organisation=parent.name, organisation_slug=parent.slug
    )


async def update_managed_centre(
    db: AsyncSession, tenant: Tenant, actor: User, data: CentreIn
) -> ManagedCentreOut:
    """A manager keeps their own centre's details true.

    The same writer the organisation uses (`update_centre`), so the rules are the same ones: a name
    unique within the organisation, a resolved place, and **a checked address that changes loses its
    mark**. A closed centre is not edited from inside: whoever closed it reopens it, and a manager
    editing a place that is not running would be news to nobody.
    """
    centre, parent = await managed_centre(db, tenant)
    if centre.closed_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This centre is closed. The organisation has to reopen it before it can be changed",
        )
    updated = await update_centre(db, parent, centre, actor, data)
    return managed_out(updated, parent)
