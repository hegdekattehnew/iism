"""Can this person actually take the course? (Sprint 58, BL-14.6, ADR-068)

Two layers, as for the scorer. `attendance.py` is pure, so its rules are pinned over literal
inputs with no database: where a course is, whether it has started or is full, whether it fits a
budget, and the order those facts give. Then `courses_closing_gap` is run against real rows to
check the pieces are connected -- and that **without a context the order is exactly what it was**,
because the employer-facing sponsorship callers know no candidate and must not change.

The rule worth the most care: a course that closes a mandatory standard is never outranked by a
nearer one that does not.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import today_ist
from api.modules.geography.models import District, State
from api.modules.identity import Tenant
from api.modules.identity.models import User
from api.modules.interests import CourseInterest
from api.modules.marketplace.models import (
    CandidatePreferredLocation,
    CandidateProfile,
    Course,
    CourseSkill,
)
from api.modules.matching import CourseSuggestionOut, attend_context, courses_closing_gap
from api.modules.matching.attendance import (
    AttendContext,
    CourseFacts,
    assess,
    rank_key,
)
from api.modules.matching.scoring import MissingSkill
from api.modules.skills.models import Skill

TODAY = date(2026, 10, 13)
HOME_STATE, HOME_DISTRICT = uuid.uuid4(), uuid.uuid4()
OTHER_STATE, OTHER_DISTRICT = uuid.uuid4(), uuid.uuid4()
SAME_STATE_OTHER_DISTRICT = uuid.uuid4()


def ctx(
    *,
    states: tuple[uuid.UUID, ...] = (HOME_STATE,),
    districts: tuple[uuid.UUID, ...] = (HOME_DISTRICT,),
    budget: int | None = None,
) -> AttendContext:
    return AttendContext(
        states=frozenset(states), districts=frozenset(districts), budget_inr=budget, today=TODAY
    )


def facts(**over: object) -> CourseFacts:
    base: dict[str, object] = {
        "mode": "offline",
        "state_id": HOME_STATE,
        "district_id": HOME_DISTRICT,
        "starts_on": None,
        "seats_left": None,
        "fee_inr": 1000,
    }
    return CourseFacts(**{**base, **over})  # type: ignore[arg-type]


class TestWhereIsIt:
    def test_online_is_reachable_from_anywhere(self) -> None:
        a = assess(facts(mode="online", state_id=OTHER_STATE, district_id=OTHER_DISTRICT), ctx())
        assert a.reach == "online" and a.attendable

    def test_the_candidates_own_district(self) -> None:
        assert assess(facts(), ctx()).reach == "district"

    def test_the_candidates_state_but_another_district(self) -> None:
        a = assess(facts(district_id=SAME_STATE_OTHER_DISTRICT), ctx())
        assert a.reach == "state" and a.attendable

    def test_another_state_is_elsewhere_and_not_attendable(self) -> None:
        a = assess(facts(state_id=OTHER_STATE, district_id=OTHER_DISTRICT), ctx())
        assert a.reach == "elsewhere" and not a.attendable

    def test_hybrid_is_placed_like_offline(self) -> None:
        a = assess(facts(mode="hybrid", state_id=OTHER_STATE, district_id=OTHER_DISTRICT), ctx())
        assert a.reach == "elsewhere"

    def test_a_course_that_states_no_place_is_unknown_and_still_attendable(self) -> None:
        a = assess(facts(state_id=None, district_id=None), ctx())
        assert a.reach == "unknown" and a.attendable

    def test_a_candidate_with_no_location_gets_no_judgement_from_place(self) -> None:
        a = assess(
            facts(state_id=OTHER_STATE, district_id=OTHER_DISTRICT), ctx(states=(), districts=())
        )
        assert a.reach == "unknown" and a.attendable

    def test_a_preferred_district_in_another_state_counts_as_near(self) -> None:
        a = assess(
            facts(state_id=OTHER_STATE, district_id=OTHER_DISTRICT),
            ctx(states=(HOME_STATE, OTHER_STATE), districts=(HOME_DISTRICT, OTHER_DISTRICT)),
        )
        assert a.reach == "district"


class TestWhenAndHowMany:
    @pytest.mark.parametrize(
        ("starts_on", "started"),
        [
            (TODAY - timedelta(days=1), True),
            (TODAY, False),
            (TODAY + timedelta(days=1), False),
            (None, False),
        ],
    )
    def test_a_past_start_date_is_started_and_today_is_not(
        self, starts_on: date | None, started: bool
    ) -> None:
        a = assess(facts(starts_on=starts_on), ctx())
        assert a.started is started and a.attendable is (not started)

    @pytest.mark.parametrize(("left", "full"), [(0, True), (1, False), (None, False)])
    def test_no_seat_left_is_full_and_no_count_is_not(self, left: int | None, full: bool) -> None:
        a = assess(facts(seats_left=left), ctx())
        assert a.full is full and a.attendable is (not full)


class TestBudget:
    def test_no_budget_means_no_verdict_rather_than_over(self) -> None:
        assert assess(facts(fee_inr=999_999), ctx()).within_budget is None

    def test_a_fee_equal_to_the_budget_fits(self) -> None:
        assert assess(facts(fee_inr=1000), ctx(budget=1000)).within_budget is True

    def test_a_fee_over_the_budget_is_not_attendable(self) -> None:
        a = assess(facts(fee_inr=1001), ctx(budget=1000))
        assert a.within_budget is False and not a.attendable

    def test_a_course_with_no_stated_fee_is_free(self) -> None:
        assert assess(facts(fee_inr=None), ctx(budget=0)).within_budget is True


def key(
    a_facts: CourseFacts,
    *,
    mandatory: int,
    closes: int,
    title: str = "T",
    c: AttendContext | None = None,
):
    return rank_key(
        assess(a_facts, c or ctx()), covers_mandatory=mandatory, closes_count=closes, title=title
    )


class TestTheOrder:
    def test_a_mandatory_closer_is_never_outranked_by_a_nearer_course_that_closes_none(
        self,
    ) -> None:
        far_but_unblocks = key(
            facts(state_id=OTHER_STATE, district_id=OTHER_DISTRICT), mandatory=1, closes=1
        )
        next_door_but_not = key(facts(), mandatory=0, closes=9)
        assert far_but_unblocks < next_door_but_not

    def test_among_closers_the_one_you_can_attend_comes_first(self) -> None:
        attendable = key(facts(), mandatory=1, closes=1)
        started = key(facts(starts_on=TODAY - timedelta(days=5)), mandatory=3, closes=3)
        assert attendable < started

    def test_then_the_nearer(self) -> None:
        near = key(facts(), mandatory=1, closes=1)
        state = key(facts(district_id=SAME_STATE_OTHER_DISTRICT), mandatory=1, closes=1)
        unknown = key(facts(state_id=None, district_id=None), mandatory=1, closes=1)
        assert near < state < unknown

    def test_then_how_much_of_the_gap_it_closes_and_finally_the_title(self) -> None:
        more = key(facts(), mandatory=2, closes=2, title="Z")
        less = key(facts(), mandatory=1, closes=3, title="A")
        assert more < less
        assert key(facts(), mandatory=1, closes=1, title="A") < key(
            facts(), mandatory=1, closes=1, title="B"
        )

    def test_online_ties_with_your_own_district(self) -> None:
        assert key(facts(mode="online"), mandatory=1, closes=1) == key(
            facts(), mandatory=1, closes=1
        )


# ------------------------------------------------------------ against real rows


@pytest.fixture
async def world(db: AsyncSession) -> dict[str, object]:
    n = uuid.uuid4().int % 90_000 + 1000
    home = State(state_code=n, slug=f"home-{n}", name=f"Home{n}")
    away = State(state_code=n + 1, slug=f"away-{n}", name=f"Away{n}")
    db.add_all([home, away])
    await db.flush()
    here = District(district_code=n * 10, name=f"Here{n}", state_id=home.id)
    near = District(district_code=n * 10 + 1, name=f"Near{n}", state_id=home.id)
    far = District(district_code=n * 10 + 2, name=f"Far{n}", state_id=away.id)
    tenant = Tenant(slug=f"prov-{n}", name="Prov", tenant_type="course_provider")
    db.add_all([here, near, far, tenant])
    mandatory = Skill(
        slug=f"mand-{n}",
        name="Mandatory standard",
        skill_type="technical",
        nsqf_level=Decimal("3"),
        nos_code=f"ATT/N{n}",
        source="nsqf",
    )
    optional = Skill(
        slug=f"opt-{n}",
        name="Optional standard",
        skill_type="technical",
        nsqf_level=Decimal("3"),
        nos_code=f"ATT/M{n}",
        source="nsqf",
    )
    db.add_all([mandatory, optional])
    await db.commit()
    return {
        "home": home,
        "away": away,
        "here": here,
        "near": near,
        "far": far,
        "tenant": tenant,
        "mandatory": mandatory,
        "optional": optional,
    }


def missing(world: dict[str, object]) -> list[MissingSkill]:
    out = []
    for key_, is_mandatory in (("mandatory", True), ("optional", False)):
        s: Skill = world[key_]  # type: ignore[assignment]
        out.append(
            MissingSkill(
                skill_id=s.id,
                concept_id=s.concept_id,
                nos_code=s.nos_code,
                name=s.name,
                importance=3,
                is_mandatory=is_mandatory,
                nsqf_level=s.nsqf_level,
            )
        )
    return out


async def add_course(
    db: AsyncSession, world: dict[str, object], title: str, teaches: list[str], **over: object
) -> Course:
    tenant: Tenant = world["tenant"]  # type: ignore[assignment]
    course = Course(
        **{
            "slug": f"c-{uuid.uuid4().hex[:10]}",
            "tenant_id": tenant.id,
            "title": title,
            "status": "published",
            "mode": "offline",
            **over,
        }  # type: ignore[arg-type]
    )
    db.add(course)
    await db.flush()
    for name in teaches:
        skill: Skill = world[name]  # type: ignore[assignment]
        db.add(CourseSkill(course_id=course.id, skill_id=skill.id, level_taught=Decimal("3")))
    await db.commit()
    return course


def context_for(world: dict[str, object], **over: object) -> AttendContext:
    home: State = world["home"]  # type: ignore[assignment]
    here: District = world["here"]  # type: ignore[assignment]
    base: dict[str, object] = {
        "states": frozenset({home.id}),
        "districts": frozenset({here.id}),
        "budget_inr": None,
        "today": today_ist(),
    }
    return AttendContext(**{**base, **over})  # type: ignore[arg-type]


def titles(suggestions: list) -> list[str]:
    return [s.course.title for s in suggestions]


class TestAgainstRealRows:
    async def test_without_a_context_the_order_is_what_it_always_was(
        self, db: AsyncSession, world: dict[str, object]
    ) -> None:
        far: District = world["far"]  # type: ignore[assignment]
        away: State = world["away"]  # type: ignore[assignment]
        here: District = world["here"]  # type: ignore[assignment]
        home: State = world["home"]  # type: ignore[assignment]
        await add_course(
            db, world, "B near, closes 1", ["optional"], state_id=home.id, district_id=here.id
        )
        await add_course(
            db,
            world,
            "A far, closes both",
            ["mandatory", "optional"],
            state_id=away.id,
            district_id=far.id,
        )
        result = await courses_closing_gap(db, missing(world))
        assert titles(result) == ["A far, closes both", "B near, closes 1"]

    async def test_without_a_context_a_started_course_is_not_demoted(
        self, db: AsyncSession, world: dict[str, object]
    ) -> None:
        """What the sponsorship callers rely on: they know no candidate, so nothing may reorder."""
        started = today_ist() - timedelta(days=30)
        await add_course(
            db, world, "Started, closes both", ["mandatory", "optional"], starts_on=started
        )
        await add_course(db, world, "Open, closes one", ["mandatory"])
        result = await courses_closing_gap(db, missing(world))
        assert titles(result) == ["Started, closes both", "Open, closes one"]
        with_context = await courses_closing_gap(db, missing(world), attend=context_for(world))
        assert titles(with_context) == ["Open, closes one", "Started, closes both"]

    async def test_a_mandatory_closer_far_away_still_beats_a_nearby_course_that_closes_none(
        self, db: AsyncSession, world: dict[str, object]
    ) -> None:
        far: District = world["far"]  # type: ignore[assignment]
        away: State = world["away"]  # type: ignore[assignment]
        here: District = world["here"]  # type: ignore[assignment]
        home: State = world["home"]  # type: ignore[assignment]
        await add_course(
            db, world, "Nearby, optional only", ["optional"], state_id=home.id, district_id=here.id
        )
        await add_course(
            db, world, "Faraway, unblocks", ["mandatory"], state_id=away.id, district_id=far.id
        )
        result = await courses_closing_gap(db, missing(world), attend=context_for(world))
        assert titles(result) == ["Faraway, unblocks", "Nearby, optional only"]
        assert [s.attendance.attendable for s in result] == [False, True]

    async def test_among_courses_that_unblock_the_attendable_and_nearer_ones_come_first(
        self, db: AsyncSession, world: dict[str, object]
    ) -> None:
        far: District = world["far"]  # type: ignore[assignment]
        away: State = world["away"]  # type: ignore[assignment]
        here: District = world["here"]  # type: ignore[assignment]
        near: District = world["near"]  # type: ignore[assignment]
        home: State = world["home"]  # type: ignore[assignment]
        yesterday = today_ist() - timedelta(days=1)
        await add_course(db, world, "5 far", ["mandatory"], state_id=away.id, district_id=far.id)
        await add_course(
            db,
            world,
            "4 started",
            ["mandatory"],
            state_id=home.id,
            district_id=here.id,
            starts_on=yesterday,
        )
        await add_course(db, world, "3 state", ["mandatory"], state_id=home.id, district_id=near.id)
        await add_course(db, world, "2 online", ["mandatory"], mode="online")
        await add_course(
            db, world, "1 district", ["mandatory"], state_id=home.id, district_id=here.id
        )
        result = await courses_closing_gap(db, missing(world), attend=context_for(world), limit=10)
        assert titles(result)[:3] == ["1 district", "2 online", "3 state"]
        assert titles(result)[3:] == ["4 started", "5 far"] or titles(result)[3:] == [
            "5 far",
            "4 started",
        ]

    async def test_a_full_course_is_ranked_after_an_open_one_and_says_so(
        self, db: AsyncSession, world: dict[str, object]
    ) -> None:
        here: District = world["here"]  # type: ignore[assignment]
        home: State = world["home"]  # type: ignore[assignment]
        full = await add_course(
            db, world, "A full", ["mandatory"], state_id=home.id, district_id=here.id, seats=1
        )
        await add_course(
            db, world, "B open", ["mandatory"], state_id=home.id, district_id=here.id, seats=5
        )
        user = User(phone=f"+91{9000000000 + uuid.uuid4().int % 999_999_999}")
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        await db.flush()
        db.add(CourseInterest(course_id=full.id, profile_id=profile.id, status="enrolled"))
        await db.commit()

        result = await courses_closing_gap(db, missing(world), attend=context_for(world))
        assert titles(result) == ["B open", "A full"]
        assert (result[0].seats_left, result[1].seats_left) == (5, 0)
        assert result[1].attendance.full and not result[1].attendance.attendable

    async def test_an_over_budget_course_is_ranked_after_an_affordable_one(
        self, db: AsyncSession, world: dict[str, object]
    ) -> None:
        here: District = world["here"]  # type: ignore[assignment]
        home: State = world["home"]  # type: ignore[assignment]
        await add_course(
            db,
            world,
            "A dear",
            ["mandatory"],
            state_id=home.id,
            district_id=here.id,
            fee_inr=50_000,
        )
        await add_course(
            db,
            world,
            "B cheap",
            ["mandatory"],
            state_id=home.id,
            district_id=here.id,
            fee_inr=2_000,
        )
        result = await courses_closing_gap(
            db, missing(world), attend=context_for(world, budget_inr=5_000)
        )
        assert titles(result) == ["B cheap", "A dear"]
        assert [s.attendance.within_budget for s in result] == [True, False]

    async def test_every_suggestion_says_where_when_and_how_many_places(
        self, db: AsyncSession, world: dict[str, object]
    ) -> None:
        here: District = world["here"]  # type: ignore[assignment]
        home: State = world["home"]  # type: ignore[assignment]
        starts = today_ist() + timedelta(days=9)
        await add_course(
            db,
            world,
            "Placed",
            ["mandatory"],
            state_id=home.id,
            district_id=here.id,
            location_state=home.name,
            location_district=here.name,
            starts_on=starts,
            seats=12,
            fee_inr=3000,
        )
        [suggestion] = await courses_closing_gap(db, missing(world), attend=context_for(world))
        out = CourseSuggestionOut.from_suggestion(suggestion)
        assert (out.location_state, out.location_district) == (home.name, here.name)
        assert (out.starts_on, out.seats_left, out.fee_inr) == (starts, 12, 3000)
        assert (out.reach, out.started, out.full, out.attendable) == (
            "district",
            False,
            False,
            True,
        )

    async def test_attend_context_reads_the_profile_and_the_preferred_places(
        self, db: AsyncSession, world: dict[str, object]
    ) -> None:
        home: State = world["home"]  # type: ignore[assignment]
        here: District = world["here"]  # type: ignore[assignment]
        far: District = world["far"]  # type: ignore[assignment]
        away: State = world["away"]  # type: ignore[assignment]
        user = User(phone=f"+91{9000000000 + uuid.uuid4().int % 999_999_999}")
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id, state_id=home.id, district_id=here.id)
        db.add(profile)
        await db.flush()
        db.add(
            CandidatePreferredLocation(
                profile_id=profile.id, state="x", state_id=away.id, district_id=far.id
            )
        )
        await db.commit()
        built = await attend_context(db, profile.id, 4_000)
        assert built.states == {home.id, away.id}
        assert built.districts == {here.id, far.id}
        assert built.budget_inr == 4_000 and built.today == today_ist()
