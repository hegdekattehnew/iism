"""The district skill-gap view (Sprint 49, BL-12.7).

The rules worth pinning are the ones that protect a person: a small count of
residents in a place nearly describes them, so it is not shown, and nothing beside it
may let the reader subtract it back out. Everything else is arithmetic on public
vacancies.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.geography.models import District, State
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, CandidateSkill, Job, JobSkill
from api.modules.operations.skill_gap import (
    MIN_CELL_SIZE,
    district_skill_gap,
    districts_with_demand,
    rank_gaps,
    suppress,
)
from api.modules.skills.concepts import SkillConcept
from api.modules.skills.models import Skill
from tests.test_operations import _candidate, _operator


class TestSuppression:
    def test_one_to_four_are_hidden_and_the_rest_shown(self) -> None:
        assert [suppress(n) for n in (0, 1, 4, 5, 6, 400)] == [
            (0, False),
            (None, True),
            (None, True),
            (5, False),
            (6, False),
            (400, False),
        ]

    def test_the_floor_is_five(self) -> None:
        assert MIN_CELL_SIZE == 5

    def test_a_hidden_supply_is_never_recoverable_from_the_shortfall(self) -> None:
        """Demand is public, so a shortfall computed from the true supply would hand it
        back. It is computed against the largest hidden value -- four -- whether the
        true supply was one or four."""
        a, b = (uuid.uuid4(), uuid.uuid4())
        demand = {
            a: ("X/N1", "One resident", 1, 10),
            b: ("X/N2", "Four residents", 1, 10),
        }
        rows = {r.name: r for r in rank_gaps(demand, {a: 1, b: 4})}

        assert rows["One resident"].shortfall == rows["Four residents"].shortfall == 6
        assert rows["One resident"].supply is None
        assert rows["One resident"].shortfall_is_minimum is True

    def test_rows_are_ranked_on_what_is_shown_so_the_order_leaks_nothing(self) -> None:
        """Two standards with the same demand and different hidden supplies must
        come out in name order, not supply order. If they were ranked on the true
        supply, 'Z' (one resident) would lead 'A' (four) and the order would tell
        the reader which is smaller."""
        a, z = uuid.uuid4(), uuid.uuid4()
        rows = rank_gaps(
            {a: ("X/N1", "A", 1, 10), z: ("X/N2", "Z", 1, 10)},
            {a: 4, z: 1},
        )
        assert [r.name for r in rows] == ["A", "Z"]

    def test_zero_is_shown_because_an_absence_describes_nobody(self) -> None:
        key = uuid.uuid4()
        (row,) = rank_gaps({key: ("X/N1", "Nobody", 2, 7)}, {})
        assert row.supply == 0
        assert row.supply_below_minimum is False
        assert row.shortfall == 7
        assert row.shortfall_is_minimum is False

    def test_ranking_is_by_shortfall_then_demand_with_no_threshold(self) -> None:
        keys = [uuid.uuid4() for _ in range(4)]
        rows = rank_gaps(
            {
                keys[0]: (None, "Covered", 1, 3),
                keys[1]: (None, "Wide", 1, 20),
                keys[2]: (None, "Narrow", 1, 6),
                keys[3]: (None, "Wide too", 1, 20),
            },
            {keys[0]: 9, keys[1]: 5, keys[2]: 0, keys[3]: 5},
        )
        # Wide 15, Wide too 15, Narrow 6, Covered 0. The covered one is *listed*, last.
        assert [r.name for r in rows] == ["Wide", "Wide too", "Narrow", "Covered"]
        assert [r.shortfall for r in rows] == [15, 15, 6, 0]


async def _world(db: AsyncSession) -> dict:
    state = State(state_code=9801, name="Gap State", slug="gap-state")
    db.add(state)
    await db.flush()
    d1 = District(district_code=98011, name="Gap Town", state_id=state.id)
    d2 = District(district_code=98012, name="Small Town", state_id=state.id)
    db.add_all([d1, d2])
    concept = SkillConcept(slug="gap-twin", normalised_name="twin", name="Twin")
    db.add(concept)
    await db.flush()
    skills = {
        "s1": Skill(slug="gap-s1", name="Alpha", skill_type="technical", nos_code="GAP/N1"),
        "s2": Skill(slug="gap-s2", name="Bravo", skill_type="technical", nos_code="GAP/N2"),
        "t1": Skill(
            slug="gap-t1",
            name="Charlie",
            skill_type="technical",
            nos_code="GAP/N3",
            concept_id=concept.id,
        ),
        "t2": Skill(
            slug="gap-t2",
            name="Charlie reissue",
            skill_type="technical",
            nos_code="GAP/N4",
            concept_id=concept.id,
        ),
    }
    for s in skills.values():
        s.nsqf_level = Decimal("3")
        s.source = "nsqf"
    db.add_all(skills.values())
    tenant = Tenant(slug="gap-employer", name="Gap Employer", tenant_type="employer")
    db.add(tenant)
    await db.flush()

    async def job(slug: str, district: District, positions: int, needs: list[Skill], **kw) -> Job:  # type: ignore[no-untyped-def]
        j = Job(
            slug=slug,
            tenant_id=tenant.id,
            title=slug,
            employment_type="full_time",
            status="published",
            state_id=state.id,
            district_id=district.id,
            positions=positions,
            **kw,
        )
        db.add(j)
        await db.flush()
        for s in needs:
            db.add(JobSkill(job_id=j.id, skill_id=s.id, importance=3, is_mandatory=False))
        await db.flush()
        return j

    await job("gap-j1", d1, 9, [skills["s1"], skills["s2"]])
    # Lists *both* rows of one concept: it is one standard, and counts once.
    await job("gap-j2", d1, 2, [skills["s1"], skills["t1"], skills["t2"]])
    # Closed: no longer anybody's demand.
    await job(
        "gap-closed",
        d1,
        50,
        [skills["s2"]],
        closed_at=datetime.now(UTC),
        close_reason="filled",
    )
    await job("gap-j4", d2, 4, [skills["s1"]])

    n = 0

    async def resident(district: District, holds: list[Skill]) -> None:
        nonlocal n
        n += 1
        user = User(phone=f"+9197{n:08d}")
        db.add(user)
        await db.flush()
        p = CandidateProfile(
            user_id=user.id, headline=f"r{n}", state_id=state.id, district_id=district.id
        )
        db.add(p)
        await db.flush()
        for s in holds:
            db.add(CandidateSkill(profile_id=p.id, skill_id=s.id, proficiency=3))
        await db.flush()

    for _ in range(6):
        await resident(d1, [skills["s1"]])  # six hold Alpha: a number may be shown
    for _ in range(3):
        await resident(d1, [skills["s2"]])  # three hold Bravo: it may not
    await resident(d2, [skills["s1"]])
    await resident(d2, [skills["s1"]])  # two live in the small town
    await db.commit()
    return {"d1": d1, "d2": d2, "skills": skills}


class TestTheGap:
    async def test_demand_counts_open_vacancies_in_the_district_only(
        self, db: AsyncSession
    ) -> None:
        w = await _world(db)
        gap = await district_skill_gap(db, w["d1"].id)
        assert gap is not None
        rows = {r.name: r for r in gap.standards}

        # Alpha: j1 (9) + j2 (2). The other district's vacancy and the closed one
        # (which asks for Bravo, 50) are not demand here.
        assert (rows["Alpha"].vacancies, rows["Alpha"].demand) == (2, 11)
        assert (rows["Bravo"].vacancies, rows["Bravo"].demand) == (1, 9)
        assert gap.vacancies == 2
        assert gap.positions == 11

    async def test_a_concept_listed_twice_by_one_vacancy_counts_once(
        self, db: AsyncSession
    ) -> None:
        w = await _world(db)
        gap = await district_skill_gap(db, w["d1"].id)
        assert gap is not None
        twin = [r for r in gap.standards if r.name.startswith("Charlie")]
        assert len(twin) == 1
        assert (twin[0].vacancies, twin[0].demand) == (1, 2)

    async def test_supply_is_residents_of_this_district_and_small_counts_are_hidden(
        self, db: AsyncSession
    ) -> None:
        w = await _world(db)
        gap = await district_skill_gap(db, w["d1"].id)
        assert gap is not None
        rows = {r.name: r for r in gap.standards}

        assert rows["Alpha"].supply == 6  # not 8: two holders live elsewhere
        assert rows["Alpha"].shortfall == 5
        assert rows["Bravo"].supply is None
        assert rows["Bravo"].supply_below_minimum is True
        assert rows["Bravo"].shortfall == 5  # 9 - 4, a minimum
        assert rows["Bravo"].shortfall_is_minimum is True
        assert rows["Charlie"].supply == 0
        assert rows["Charlie"].shortfall == 2
        assert gap.residents == 9
        assert [r.name for r in gap.standards][0] == "Alpha"  # 11 demand beats 9 on a tie

    async def test_the_total_is_suppressed_like_every_other_count(self, db: AsyncSession) -> None:
        w = await _world(db)
        gap = await district_skill_gap(db, w["d2"].id)
        assert gap is not None
        assert gap.residents is None
        assert gap.residents_below_minimum is True
        assert gap.standards[0].supply is None

    async def test_the_picker_lists_districts_with_an_open_vacancy(self, db: AsyncSession) -> None:
        await _world(db)
        options = {o.district: o.vacancies for o in await districts_with_demand(db)}
        assert options["Gap Town"] == 2
        assert options["Small Town"] == 1

    async def test_an_unknown_district_is_none(self, db: AsyncSession) -> None:
        assert await district_skill_gap(db, uuid.uuid4()) is None


class TestWhoMayRead:
    async def test_a_support_operator_reads_it_and_the_hidden_count_is_absent(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        w = await _world(db)
        headers = await _operator(client, db, tier="support")

        picker = await client.get("/ops/districts", headers=headers)
        assert picker.status_code == 200
        assert {d["name"] for d in picker.json()["districts"]} >= {"Gap Town", "Small Town"}

        response = await client.get(f"/ops/districts/{w['d1'].id}/skill-gap", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["minimum_cell"] == 5
        bravo = next(r for r in body["standards"] if r["name"] == "Bravo")
        assert bravo["supply"] is None
        assert bravo["supply_below_minimum"] is True
        # The true count (3) is nowhere in the row.
        assert 3 not in [v for k, v in bravo.items() if isinstance(v, int) and k != "vacancies"]

    async def test_a_stranger_gets_the_plain_404(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        w = await _world(db)
        headers = await _candidate(client)
        unrouted = await client.get("/ops/definitely-not-a-route", headers=headers)
        for path in ("/ops/districts", f"/ops/districts/{w['d1'].id}/skill-gap"):
            refused = await client.get(path, headers=headers)
            assert refused.status_code == unrouted.status_code == 404
            assert refused.json() == unrouted.json()

    async def test_anonymous_is_401(self, client: AsyncClient) -> None:
        assert (await client.get("/ops/districts")).status_code == 401

    async def test_an_unknown_district_is_404_for_an_operator(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        headers = await _operator(client, db, tier="support")
        missing = await client.get(f"/ops/districts/{uuid.uuid4()}/skill-gap", headers=headers)
        assert missing.status_code == 404
