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

**A district name is not unique, and looking one up by name alone was wrong.**
Three names in the master each belong to two districts: Bilaspur (Chhattisgarh
and Himachal Pradesh), Hamirpur (Himachal Pradesh and Uttar Pradesh) and
Pratapgarh (Rajasthan and Uttar Pradesh). The query here was
`where(lower(name) == key).limit(1)` with no ORDER BY, so Postgres returned
whichever row it reached first and "Bilaspur, Chhattisgarh" could carry
Himachal's id. `matching._locality` compares ids and nothing else, so it would
then score that vacancy 2 — "in your district" — for somebody 1,500 km away.

`PlaceIndex` holds the rule and `resolve_location` is one of its two callers.
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.geography.models import District, State

# A spelling bridge, not a way to force a match. Only entries that are
# genuinely the same place belong here.
#
# **The one copy.** The NSQF importer used to carry a second, and a test
# asserted the two agreed -- which kept the letters in step and not the
# algorithm: the service tried the literal name then the alias, the importer
# tried both in one expression, and neither constrained by state. Both now
# resolve through `PlaceIndex`, so there is no second map and no second rule.
DISTRICT_ALIASES = {
    "bengaluru": "bengaluru urban",
    "bangalore": "bengaluru urban",
}


def _key(value: str | None) -> str:
    return (value or "").strip().lower()


@dataclass(frozen=True)
class ResolvedLocation:
    state_id: uuid.UUID | None
    district_id: uuid.UUID | None


@dataclass(frozen=True)
class _DistrictEntry:
    district_id: uuid.UUID
    state_id: uuid.UUID


@dataclass(frozen=True)
class PlaceIndex:
    """The resolution rule, over whatever slice of the master it was built from.

    Pure and session-free, so the two readers of the master cannot disagree:
    `resolve_location` answers one write, `load_place_index` feeds the NSQF
    importer's sweep over every existing row, and both apply *this*.

    The rule, in three lines:

    - when the state resolves, only a district **in that state** may match;
    - when it does not, a name matches only if exactly one district bears it;
    - otherwise the district stays unresolved.

    **No id is better than a wrong one.** The free text is kept either way, so
    an unresolved district still reads correctly on the page; a wrong one is a
    factual claim ("in your district") that the data does not support.
    """

    states: Mapping[str, uuid.UUID]
    districts: Mapping[str, tuple[_DistrictEntry, ...]]

    @classmethod
    def build(
        cls,
        states: Iterable[tuple[str | None, uuid.UUID]],
        districts: Iterable[tuple[str | None, uuid.UUID, uuid.UUID]],
    ) -> "PlaceIndex":
        """`states` as `(name, id)`, `districts` as `(name, id, state_id)`.

        Unnamed rows are skipped in both: eight of the 766 districts carry no
        name, and nothing anybody writes can resolve to them.
        """
        by_state: dict[str, uuid.UUID] = {}
        for name, state_id in states:
            if key := _key(name):
                by_state.setdefault(key, state_id)

        by_district: dict[str, list[_DistrictEntry]] = {}
        for name, district_id, state_id in districts:
            if key := _key(name):
                by_district.setdefault(key, []).append(_DistrictEntry(district_id, state_id))

        return cls(
            states=by_state,
            districts={k: tuple(v) for k, v in by_district.items()},
        )

    def resolve(self, state_name: str | None, district_name: str | None) -> ResolvedLocation:
        """Best-effort. Either half may resolve without the other."""
        state_id = self.states.get(_key(state_name)) or None

        district_id: uuid.UUID | None = None
        key = _key(district_name)
        if key:
            # The written name first, then its alias -- and each filtered by
            # the state when there is one, so an alias can never reach across
            # a border either.
            for name in (key, DISTRICT_ALIASES.get(key)):
                if name is None:
                    continue
                entries = self.districts.get(name, ())
                if state_id is not None:
                    entries = tuple(e for e in entries if e.state_id == state_id)
                if entries:
                    # More than one and no state to choose between them: the
                    # name is genuinely ambiguous and guessing is the bug.
                    if len(entries) == 1:
                        district_id = entries[0].district_id
                    break

        return ResolvedLocation(state_id=state_id, district_id=district_id)


async def load_place_index(db: AsyncSession) -> PlaceIndex:
    """The whole master — for resolving many rows at once (the import backfill).

    36 states and 766 districts, so a few hundred kilobytes. `resolve_location`
    deliberately does *not* use this: one write should not read the master.
    """
    states = (await db.execute(select(State.name, State.id))).all()
    districts = (await db.execute(select(District.name, District.id, District.state_id))).all()
    return PlaceIndex.build(
        ((row.name, row.id) for row in states),
        ((row.name, row.id, row.state_id) for row in districts),
    )


async def resolve_location(
    db: AsyncSession, state_name: str | None, district_name: str | None
) -> ResolvedLocation:
    """Best-effort. Either half may resolve without the other.

    Loads only the rows these two names could reach — every district bearing
    the written name or its alias, in **any** state, so `PlaceIndex` can see
    that a name is ambiguous — then applies the same rule the import backfill
    does. The signature is unchanged from the version that looked a district up
    by name alone, so none of its six callers needed touching.
    """
    names = [n for n in (_key(district_name), DISTRICT_ALIASES.get(_key(district_name))) if n]

    state_key = _key(state_name)
    states = (
        (
            await db.execute(
                select(State.name, State.id).where(func.lower(State.name) == state_key)
            )
        ).all()
        if state_key
        else []
    )
    districts = (
        (
            await db.execute(
                select(District.name, District.id, District.state_id).where(
                    or_(*(func.lower(District.name) == n for n in names))
                )
            )
        ).all()
        if names
        else []
    )

    index = PlaceIndex.build(
        ((row.name, row.id) for row in states),
        ((row.name, row.id, row.state_id) for row in districts),
    )
    return index.resolve(state_name, district_name)


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
