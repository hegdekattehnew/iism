"""Where a district's vacancies ask for standards its residents do not hold (BL-12.7).

A district official's question is not "which standards are scarce" -- that needs a
threshold nobody has a basis for -- but "of what employers here want, where is the
gap widest". So every standard an open vacancy in the district requires is listed and
**ranked by shortfall**; nothing is excluded for falling under a line.

* **Demand** is the head-count (`Job.positions`) of the district's *open* vacancies
  (`open_job()`, the predicate every listing uses) that require the standard.
  Vacancies are public listings; this discloses nothing about a person.
* **Supply** is the number of distinct residents -- `CandidateProfile.district_id`,
  where they live, not where they said they would work -- who hold it, compared at
  concept level as the scorer does.
* **Shortfall** is `demand - supply`, floored at zero. It is *per standard*: one
  resident holds several, so the column does not add up to a number of people.

**Small counts are suppressed (`MIN_CELL_SIZE`).** Supply is a count of people in a
place; in a small district "2 residents hold this" is nearly a description of them. A
supply of 1 to 4 is therefore reported as *fewer than five*, not as a number. Showing
the demand beside a suppressed supply would let the reader subtract it back, so the
shortfall is then computed against the largest hidden value (4) and flagged as a
minimum -- and rows are ranked on what is *shown*, so the order leaks no more than the
figures. A supply of exactly zero is shown: nobody is described by an absence. The
total of residents is suppressed the same way.

This is operator-only, beside the programme report, so the audience is the one that
already sees district data (`OPS_PROGRAMME_READ`).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.geography.models import District, State
from api.modules.marketplace.models import (
    CandidateProfile,
    CandidateSkill,
    Job,
    JobSkill,
    open_job,
)
from api.modules.skills.models import Skill

# Counts below this (and above zero) are not shown. Five is the floor the statistical
# agencies this product's audience works with commonly use for published small cells.
MIN_CELL_SIZE = 5

# Ids per `IN (...)`: well under asyncpg's 32,767 bind parameters.
_IN_CHUNK = 5_000


@dataclass(frozen=True)
class GapRow:
    nos_code: str | None
    name: str
    vacancies: int
    demand: int
    supply: int | None
    """`None` when 1 to `MIN_CELL_SIZE - 1` residents hold it."""
    supply_below_minimum: bool
    shortfall: int
    shortfall_is_minimum: bool
    """True when the shortfall was computed against a hidden supply, so the real
    figure is at least this."""


@dataclass(frozen=True)
class DistrictGap:
    district_id: uuid.UUID
    district: str
    state: str | None
    vacancies: int
    positions: int
    residents: int | None
    residents_below_minimum: bool
    standards: list[GapRow]


@dataclass(frozen=True)
class DistrictOption:
    district_id: uuid.UUID
    district: str
    state: str | None
    vacancies: int


def suppress(count: int) -> tuple[int | None, bool]:
    """`(shown, below_minimum)` for a count of people. The one rule."""
    if 0 < count < MIN_CELL_SIZE:
        return None, True
    return count, False


def rank_gaps(
    demand: dict[uuid.UUID, tuple[str | None, str, int, int]],
    supply: dict[uuid.UUID, int],
) -> list[GapRow]:
    """Turn demand and true supply into the rows that may be shown, ranked.

    `demand` maps a standard's key to `(nos_code, name, vacancies, positions)`;
    `supply` its true resident-holder count (missing means nobody). Pure, so the
    suppression and the ranking can be tested without a database.
    """
    rows: list[GapRow] = []
    for key, (nos_code, name, vacancies, positions) in demand.items():
        shown, hidden = suppress(supply.get(key, 0))
        # Computed against the largest value that was hidden, never the true one.
        visible = (MIN_CELL_SIZE - 1) if hidden else (shown or 0)
        rows.append(
            GapRow(
                nos_code=nos_code,
                name=name,
                vacancies=vacancies,
                demand=positions,
                supply=shown,
                supply_below_minimum=hidden,
                shortfall=max(0, positions - visible),
                shortfall_is_minimum=hidden,
            )
        )
    rows.sort(key=lambda r: (-r.shortfall, -r.demand, r.name, r.nos_code or ""))
    return rows


def _chunks(items: list[uuid.UUID]) -> list[list[uuid.UUID]]:
    return [items[i : i + _IN_CHUNK] for i in range(0, len(items), _IN_CHUNK)]


async def districts_with_demand(db: AsyncSession, *, limit: int = 200) -> list[DistrictOption]:
    """Districts that have at least one open vacancy, most vacancies first.

    A district with none has no gap to show, and offering it in a picker leads to an
    empty screen.
    """
    count = func.count().label("n")
    rows = (
        await db.execute(
            select(District.id, District.name, State.name, count)
            .select_from(Job)
            .join(District, District.id == Job.district_id)
            .outerjoin(State, State.id == District.state_id)
            .where(open_job())
            .group_by(District.id, District.name, State.name)
            .order_by(count.desc(), District.name)
            .limit(limit)
        )
    ).all()
    return [
        DistrictOption(district_id=i, district=name or "", state=state, vacancies=n)
        for i, name, state, n in rows
    ]


async def district_skill_gap(
    db: AsyncSession, district_id: uuid.UUID, *, limit: int = 15
) -> DistrictGap | None:
    """The gap for one district, or `None` when there is no such district."""
    head = (
        await db.execute(
            select(District.name, State.name)
            .outerjoin(State, State.id == District.state_id)
            .where(District.id == district_id)
        )
    ).first()
    if head is None:
        return None

    # Demand: one row per (open vacancy, standard), de-duplicated in Python because a
    # vacancy may list two rows of one concept and must count once for it. The set is
    # a district's open vacancies times their requirements -- small.
    key = func.coalesce(Skill.concept_id, Skill.id)
    required = (
        await db.execute(
            select(Job.id, Job.positions, key, Skill.nos_code, Skill.name)
            .select_from(JobSkill)
            .join(Job, Job.id == JobSkill.job_id)
            .join(Skill, Skill.id == JobSkill.skill_id)
            .where(open_job(), Job.district_id == district_id)
            .order_by(Skill.name, Skill.nos_code)
        )
    ).all()
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    jobs: dict[uuid.UUID, int] = {}
    demand: dict[uuid.UUID, tuple[str | None, str, int, int]] = {}
    for job_id, positions, standard, nos_code, name in required:
        jobs[job_id] = positions
        if (job_id, standard) in seen:
            continue
        seen.add((job_id, standard))
        # The first row in name order stands for the standard, so the label does not
        # depend on which row the database returned first.
        code, label, vacancies, total = demand.get(standard, (nos_code, name, 0, 0))
        demand[standard] = (code, label, vacancies + 1, total + positions)

    supply: dict[uuid.UUID, int] = {}
    wanted = list(demand)
    for chunk in _chunks(wanted):
        for standard, holders in (
            await db.execute(
                select(key, func.count(func.distinct(CandidateSkill.profile_id)))
                .select_from(CandidateSkill)
                .join(Skill, Skill.id == CandidateSkill.skill_id)
                .join(CandidateProfile, CandidateProfile.id == CandidateSkill.profile_id)
                .where(
                    CandidateProfile.district_id == district_id,
                    Skill.concept_id.in_(chunk) | Skill.id.in_(chunk),
                )
                .group_by(key)
            )
        ).all():
            supply[standard] = holders
    residents = (
        await db.scalar(
            select(func.count(func.distinct(CandidateSkill.profile_id)))
            .select_from(CandidateSkill)
            .join(CandidateProfile, CandidateProfile.id == CandidateSkill.profile_id)
            .where(CandidateProfile.district_id == district_id)
        )
        or 0
    )
    shown, hidden = suppress(residents)
    return DistrictGap(
        district_id=district_id,
        district=head[0] or "",
        state=head[1],
        vacancies=len(jobs),
        positions=sum(jobs.values()),
        residents=shown,
        residents_below_minimum=hidden,
        standards=rank_gaps(demand, supply)[:limit],
    )
