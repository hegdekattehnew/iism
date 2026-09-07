"""Resolving a written place name to the geography master.

This logic previously existed only inside `_backfill_geography` in the NSQF
importer, which meant a job created through the API would carry NULL
`state_id` / `district_id` for ever — visible at `/jobs`, and **invisible to
`match_jobs(state_id=…)`**. A listing that silently cannot be found by location
is worse than one that fails loudly, so resolution now happens on write and the
importer's sweep becomes a backfill for rows that predate it.

**The foreign key sits beside the free text, never instead of it.** Not every
value resolves — the master spells Bengaluru "BENGALURU URBAN" — and an
unresolvable location is still a location.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.geography.models import District, State

# A spelling bridge, not a way to force a match. Only entries that are
# genuinely the same place belong here. Kept in step with the importer's copy,
# which is the other reader of the same master.
DISTRICT_ALIASES = {
    "bengaluru": "bengaluru urban",
    "bangalore": "bengaluru urban",
}


@dataclass(frozen=True)
class ResolvedLocation:
    state_id: uuid.UUID | None
    district_id: uuid.UUID | None


async def resolve_location(
    db: AsyncSession, state_name: str | None, district_name: str | None
) -> ResolvedLocation:
    """Best-effort. Either half may resolve without the other."""
    state_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None

    if state_name and state_name.strip():
        state_id = await db.scalar(
            select(State.id).where(func.lower(State.name) == state_name.strip().lower())
        )

    if district_name and district_name.strip():
        key = district_name.strip().lower()
        district_id = await db.scalar(
            select(District.id).where(func.lower(District.name) == key).limit(1)
        )
        if district_id is None and key in DISTRICT_ALIASES:
            district_id = await db.scalar(
                select(District.id)
                .where(func.lower(District.name) == DISTRICT_ALIASES[key])
                .limit(1)
            )

    return ResolvedLocation(state_id=state_id, district_id=district_id)


async def list_states(db: AsyncSession) -> list[State]:
    return list((await db.scalars(select(State).order_by(State.name))).all())


async def list_districts(db: AsyncSession, state_id: uuid.UUID | None = None) -> list[District]:
    """Districts, optionally within one state.

    Eight of the 766 districts carry no name — imported by code because the code
    is still a valid reference. They are excluded here: an unnamed option in a
    dropdown is not a choice anyone can make.
    """
    query = select(District).where(District.name.isnot(None)).order_by(District.name)
    if state_id is not None:
        query = query.where(District.state_id == state_id)
    return list((await db.scalars(query)).all())
