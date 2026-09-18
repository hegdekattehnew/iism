"""Matching: the scoring rules, and the endpoints that expose them.

The scorer is pure, so most of this needs no database at all — which is the
point of keeping it that way. Every case here is a rule someone could
plausibly weaken later without noticing.
"""

import math
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION as CONSENT
from api.modules.analytics.models import AnalyticsEvent
from api.modules.geography.models import District, State
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import CandidateProfile, CandidateSkill, Job, JobSkill
from api.modules.matching.scoring import (
    EXPERIENCE_WEIGHT,
    LEVEL_WEIGHT,
    MANDATORY_GAP_CAP,
    HeldSkill,
    RequiredSkill,
    score_match,
)
from api.modules.skills.models import Skill


def _req(name: str, *, importance: int = 3, mandatory: bool = False, concept=None, level=None):
    return RequiredSkill(
        skill_id=uuid.uuid4(),
        concept_id=concept,
        nos_code=f"X/{name}",
        name=name,
        nsqf_level=level,
        importance=importance,
        is_mandatory=mandatory,
    )


def _held(req: RequiredSkill, *, source: str = "certified", proficiency: int = 4):
    """A candidate holding exactly the given requirement."""
    return HeldSkill(
        skill_id=req.skill_id,
        concept_id=req.concept_id,
        name=req.name,
        proficiency=proficiency,
        source=source,
    )


class TestScoring:
    def test_holding_everything_scores_full(self) -> None:
        reqs = [_req("a"), _req("b")]
        result = score_match(reqs, [_held(r) for r in reqs])

        assert result.score == 100
        assert result.coverage == 1.0
        assert result.missing == []

    def test_holding_nothing_scores_zero(self) -> None:
        """Not a small number. Level and evidence components alone would give
        every job in the catalogue a non-zero score for everyone, which is noise
        that ranking then has to see past."""
        result = score_match([_req("a"), _req("b")], [])

        assert result.score == 0
        assert result.coverage == 0.0
        assert len(result.missing) == 2

    def test_importance_weights_coverage(self) -> None:
        """Holding the important half beats holding the unimportant half."""
        heavy, light = _req("heavy", importance=5), _req("light", importance=1)

        with_heavy = score_match([heavy, light], [_held(heavy)])
        with_light = score_match([heavy, light], [_held(light)])

        assert with_heavy.score > with_light.score

    def test_a_missing_mandatory_standard_caps_the_score(self) -> None:
        """Caps, not merely penalises. A job saying a unit is required means it."""
        reqs = [_req(f"s{i}", importance=5) for i in range(5)]
        reqs.append(_req("gate", importance=1, mandatory=True))

        result = score_match(reqs, [_held(r) for r in reqs[:5]])

        assert result.missing_mandatory == 1
        assert result.capped_by_mandatory
        assert result.score <= round(MANDATORY_GAP_CAP * 100)

    def test_the_cap_is_not_zero(self) -> None:
        """A candidate one standard short of a strong match should be told so,
        not hidden. Zero would rank them alongside someone with nothing."""
        strong = [_req(f"s{i}", importance=5) for i in range(5)]
        strong.append(_req("gate", mandatory=True))
        weak = [_req("only", mandatory=True)]

        held_strong = score_match(strong, [_held(r) for r in strong[:5]])
        held_none = score_match(weak, [])

        assert held_strong.score > held_none.score

    def test_evidence_outranks_self_declaration(self) -> None:
        """What `candidate_skills.source` was added for in Sprint 4."""
        reqs = [_req("a"), _req("b")]

        certified = score_match(reqs, [_held(r, source="certified") for r in reqs])
        declared = score_match(reqs, [_held(r, source="self_declared") for r in reqs])

        assert certified.score > declared.score

    def test_self_declaration_still_counts(self) -> None:
        """It is often all a new candidate has; discarding it empties most
        profiles."""
        reqs = [_req("a")]
        result = score_match(reqs, [_held(reqs[0], source="self_declared")])

        assert result.score > 0
        assert result.matched[0].evidence == "self_declared"

    def test_matching_happens_at_concept_level(self) -> None:
        """The whole reason the concept layer exists: a candidate and a job that
        picked different rows for the same standard must still meet."""
        concept = uuid.uuid4()
        required = _req("standard", concept=concept)
        held = HeldSkill(
            skill_id=uuid.uuid4(),  # a different row entirely
            concept_id=concept,
            name="standard, another issue of it",
            proficiency=4,
            source="certified",
        )

        result = score_match([required], [held])
        assert result.score == 100
        assert result.missing == []

    def test_a_skill_without_a_concept_matches_only_itself(self) -> None:
        """Falling back to the row id must not make unconceptualised rows match
        each other."""
        required = _req("standard", concept=None)
        other = HeldSkill(
            skill_id=uuid.uuid4(),
            concept_id=None,
            name="something else",
            proficiency=4,
            source="certified",
        )

        assert score_match([required], [other]).score == 0

    def test_level_shortfall_tapers_rather_than_cliffs(self) -> None:
        reqs = [_req("a")]
        held = [_held(reqs[0])]

        met = score_match(reqs, held, job_level_min=Decimal("3"), candidate_level=Decimal("4"))
        short = score_match(reqs, held, job_level_min=Decimal("5"), candidate_level=Decimal("4"))
        far = score_match(reqs, held, job_level_min=Decimal("7"), candidate_level=Decimal("4"))

        assert met.score > short.score > far.score
        assert short.level_shortfall == Decimal("1")

    def test_an_unknown_level_is_not_scored_as_zero(self) -> None:
        """Most profiles carry no assessed level; treating that as level 0 would
        bury every new candidate."""
        reqs = [_req("a")]
        unknown = score_match(reqs, [_held(reqs[0])], job_level_min=Decimal("4"))
        zero_ish = score_match(
            reqs, [_held(reqs[0])], job_level_min=Decimal("4"), candidate_level=Decimal("1")
        )

        assert unknown.score > zero_ish.score

    def test_a_job_with_no_requirements_scores_zero(self) -> None:
        """Returning 100 would rank empty jobs above real ones."""
        assert score_match([], [_held(_req("a"))]).score == 0

    def test_missing_is_ordered_by_what_matters(self) -> None:
        reqs = [
            _req("optional-low", importance=1),
            _req("mandatory", importance=1, mandatory=True),
            _req("optional-high", importance=5),
        ]
        result = score_match(reqs, [])

        assert [m.name for m in result.missing] == [
            "mandatory",
            "optional-high",
            "optional-low",
        ]


async def _auth(client: AsyncClient) -> dict[str, str]:
    """Same shape as tests/test_profile.py, so sign-in behaves identically."""
    phone = "9" + uuid.uuid4().int.__str__()[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (
        await client.post(
            "/auth/otp/verify", json={"phone": phone, "code": code, "consent_version": CONSENT}
        )
    ).json()
    return {"authorization": f"Bearer {body['access_token']}"}


class TestMatchEndpoints:
    async def test_matches_require_authentication(self, client) -> None:
        assert (await client.get("/me/matches")).status_code == 401

    async def test_a_profile_with_no_skills_says_so(self, db, client) -> None:
        """Not "no matches found": zero declared skills is a different state,
        and the difference is a dead end versus a next step."""
        headers = await _auth(client)
        await client.get("/me/profile", headers=headers)
        body = (await client.get("/me/matches", headers=headers)).json()

        assert body["has_skills"] is False
        assert body["items"] == []

    async def test_a_brand_new_user_reaches_matches_without_visiting_profile(
        self, db, client
    ) -> None:
        """Profiles are created lazily, so someone who signs in and comes
        straight here has none. This used to 404, which the interface renders as
        its error state -- telling every new candidate something had gone wrong
        rather than showing them the "add your skills" prompt built for exactly
        this moment."""
        headers = await _auth(client)
        response = await client.get("/me/matches", headers=headers)

        assert response.status_code == 200
        assert response.json()["has_skills"] is False

    async def test_reaching_matches_first_still_records_the_event(self, db, client) -> None:
        """The subtle half of creating the profile here: `record()` commits, so
        a half-finished write left in the session would be swept in with it.
        `ensure_profile` commits its own creation, and this is what proves the
        two do not interfere."""
        headers = await _auth(client)
        await client.get("/me/matches", headers=headers)

        recorded = await db.scalar(
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(AnalyticsEvent.name == "matches_viewed")
        )
        assert recorded == 1

    async def test_the_profile_is_actually_created(self, db, client) -> None:
        """Lazily, but really: the next request must find a row rather than
        create a second one."""
        headers = await _auth(client)
        me = (await client.get("/auth/me", headers=headers)).json()
        await client.get("/me/matches", headers=headers)
        await client.get("/me/matches", headers=headers)

        profiles = await db.scalar(
            select(func.count())
            .select_from(CandidateProfile)
            .where(CandidateProfile.user_id == uuid.UUID(me["id"]))
        )
        assert profiles == 1

    async def test_viewing_matches_records_an_event(self, db, client) -> None:
        """ADR-025: measurement substitutes for a revenue signal, and the first
        weeks of a scoring surface cannot be gathered retrospectively."""
        headers = await _auth(client)
        await client.get("/me/profile", headers=headers)
        await client.get("/me/matches", headers=headers)

        recorded = await db.scalar(
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(AnalyticsEvent.name == "matches_viewed")
        )
        assert recorded == 1


class TestEmployerConsole:
    """The scorer, run the other way round.

    The rule these guard is that there is exactly one scorer. If ranking
    candidates ever grows its own scoring logic, the two sides can disagree
    about the same pair, and neither number is defensible after that.
    """

    @pytest.fixture
    async def pool(self, db: AsyncSession) -> dict:
        """One vacancy, and three candidates who differ in exactly one way each."""
        mandatory = Skill(
            slug="infection-control-x",
            name="Infection control",
            skill_type="technical",
            nsqf_level=Decimal("4"),
            nos_code="TST/N0001",
            source="nsqf",
        )
        optional = Skill(
            slug="bed-making-x",
            name="Replace linen",
            skill_type="technical",
            nsqf_level=Decimal("3"),
            nos_code="TST/N0002",
            source="nsqf",
        )
        db.add_all([mandatory, optional])

        employer_tenant = Tenant(slug="demo-employer", name="Demo Employer", tenant_type="employer")
        db.add(employer_tenant)
        await db.flush()

        job = Job(
            slug="demo-vacancy",
            tenant_id=employer_tenant.id,
            title="Ward Attendant",
            employment_type="full_time",
            nsqf_level_min=Decimal("3"),
            status="published",
        )
        db.add(job)
        await db.flush()
        db.add_all(
            [
                JobSkill(job_id=job.id, skill_id=mandatory.id, importance=5, is_mandatory=True),
                JobSkill(job_id=job.id, skill_id=optional.id, importance=3, is_mandatory=False),
            ]
        )

        profiles = {}
        for name, rows in {
            "ready": [(mandatory, "certified"), (optional, "certified")],
            "nearly": [(optional, "certified")],
            "unrelated": [],
        }.items():
            user = User(phone=f"+9199000{abs(hash(name)) % 100000:05d}")
            db.add(user)
            await db.flush()
            profile = CandidateProfile(user_id=user.id, headline=name, years_experience=2)
            db.add(profile)
            await db.flush()
            for skill, source in rows:
                db.add(
                    CandidateSkill(
                        profile_id=profile.id,
                        skill_id=skill.id,
                        proficiency=4,
                        source=source,
                    )
                )
            profiles[name] = profile
        await db.commit()
        return {"job": job, "profiles": profiles}

    async def test_ranking_orders_by_score_and_names_the_mandatory_gap(self, pool, client) -> None:
        body = (await client.get("/employer/demo-employer/jobs/demo-vacancy/candidates")).json()

        # The candidate holding nothing the job asks for never appears: a page
        # of zeroes is not a shortlist.
        assert body["total"] == 2
        first, second = body["items"]
        assert first["score"] > second["score"]
        assert first["missing_mandatory"] == 0
        assert second["missing_mandatory"] == 1
        assert second["capped_by_mandatory"] is True
        assert [m["name"] for m in second["missing"] if m["is_mandatory"]] == ["Infection control"]

    async def test_a_candidate_is_never_identified(self, pool, client) -> None:
        """The surface is unauthenticated, so it may not carry a name, a phone
        or an email -- and a reference is enough to open a conversation."""
        body = (await client.get("/employer/demo-employer/jobs/demo-vacancy/candidates")).json()

        for card in body["items"]:
            assert card["reference"].startswith("C-")
            assert "full_name" not in card
            assert "phone" not in card
            assert "email" not in card
            assert "user_id" not in card

    async def test_both_directions_agree_on_the_same_pair(self, pool, db, client) -> None:
        """One scorer, or the explanation stops explaining anything."""
        from api.modules.matching.employer import rank_candidates
        from api.modules.matching.service import match_job_by_slug

        job = pool["job"]
        ready = pool["profiles"]["ready"]

        found = await rank_candidates(db, job.tenant_id, job.slug)
        assert found is not None
        employer_side = next(s for _, items in [found] for s in items if s.profile.id == ready.id)
        candidate_side = await match_job_by_slug(db, ready.id, job.slug)

        assert candidate_side is not None
        assert employer_side.result.score == candidate_side.result.score

    async def test_overview_counts_pool_ready_and_nearly(self, pool, client) -> None:
        body = (await client.get("/employer/demo-employer/overview")).json()

        vacancy = next(j for j in body["jobs"] if j["job"]["slug"] == "demo-vacancy")
        assert vacancy["pool"] == 2
        assert vacancy["ready"] == 1
        assert vacancy["nearly"] == 1

    async def test_scarcity_counts_supply_against_demand(self, pool, client) -> None:
        body = (await client.get("/employer/demo-employer/overview")).json()

        scarce = {s["nos_code"]: s for s in body["scarce"]}
        assert scarce["TST/N0001"]["required_by"] == 1
        assert scarce["TST/N0001"]["held_by"] == 1
        assert scarce["TST/N0002"]["held_by"] == 2

    async def test_an_unknown_employer_is_a_404(self, pool, client) -> None:
        assert (await client.get("/employer/nobody/overview")).status_code == 404


async def test_the_employer_overview_costs_the_same_for_one_vacancy_or_many(
    db: AsyncSession,
) -> None:
    """It ran four queries per published vacancy, so the first page an employer
    opens got slower with every job they posted (Sprint 20). The number of
    statements must not depend on the number of vacancies -- and batching must
    not change a single pool."""
    from sqlalchemy import event

    from api.modules.matching.employer import job_pools

    skill = Skill(
        slug="n-plus-one-x",
        name="Handle patient records",
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code="TST/N0901",
        source="nsqf",
    )
    tenant = Tenant(slug="n-plus-one-employer", name="Batch Hospital", tenant_type="employer")
    db.add_all([skill, tenant])
    await db.flush()
    for name in ("holder", "other"):
        user = User(phone=f"+9199100{abs(hash(name)) % 100000:05d}")
        db.add(user)
        await db.flush()
        profile = CandidateProfile(user_id=user.id, headline=name, years_experience=1)
        db.add(profile)
        await db.flush()
        if name == "holder":
            db.add(CandidateSkill(profile_id=profile.id, skill_id=skill.id, proficiency=3))

    async def add_job(n: int) -> None:
        job = Job(
            slug=f"n-plus-one-{n}", tenant_id=tenant.id, title=f"Clerk {n}", status="published"
        )
        db.add(job)
        await db.flush()
        db.add(JobSkill(job_id=job.id, skill_id=skill.id, importance=4, is_mandatory=True))
        await db.commit()

    statements: list[str] = []

    def count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    async def measure() -> tuple[int, list]:
        statements.clear()
        connection = (await db.connection()).sync_connection
        assert connection is not None
        event.listen(connection, "before_cursor_execute", count)
        try:
            pools = await job_pools(db, tenant.id)
        finally:
            event.remove(connection, "before_cursor_execute", count)
        return len(statements), pools

    await add_job(1)
    one, pools = await measure()
    for n in (2, 3, 4):
        await add_job(n)
    four, pools = await measure()

    assert one == four, f"{one} statements for one vacancy, {four} for four"
    assert [(p.pool, p.ready, p.nearly) for p in pools] == [(1, 1, 0)] * 4


# ------------------------------------------------------- Sprint 23: experience


class TestExperience:
    """ADR-007 always named experience. Until Sprint 23 nothing read it."""

    reqs = [_req("a", importance=5), _req("b", importance=2), _req("c", importance=3)]

    def _score(self, **kwargs) -> int:
        # Holds two of three, self-declared: a score with room to move either way.
        held = [_held(r, source="self_declared") for r in self.reqs[:2]]
        return score_match(self.reqs, held, **kwargs).score

    def test_the_reweighting_is_neutral_for_a_candidate_who_fits(self) -> None:
        """Experience was carved out of level's 0.15. For someone meeting both
        floors the two halves sum to what they replaced -- which is what kept
        every golden pair still. Compared with a tolerance because in binary
        floating point 0.08 + 0.07 is 0.15000000000000002."""
        assert math.isclose(LEVEL_WEIGHT + EXPERIENCE_WEIGHT, 0.15)
        assert self._score(job_min_years=2, candidate_years=2) == self._score()

    def test_being_short_tapers_rather_than_cliffs(self) -> None:
        met = self._score(job_min_years=3, candidate_years=3)
        scores = [self._score(job_min_years=3, candidate_years=y) for y in (2, 1, 0)]
        assert met > scores[0] > scores[1] > scores[2]
        # Three years short is the floor of the taper: the whole component, no more.
        assert met - scores[2] == round(EXPERIENCE_WEIGHT * 100)

    def test_the_shortfall_is_reported_in_years(self) -> None:
        held = [_held(r) for r in self.reqs]
        result = score_match(self.reqs, held, job_min_years=4, candidate_years=1)
        assert result.experience_shortfall == 3
        assert (
            score_match(self.reqs, held, job_min_years=1, candidate_years=4).experience_shortfall
            is None
        )

    def test_a_job_asking_for_no_experience_never_penalises(self) -> None:
        assert self._score(job_min_years=0, candidate_years=0) == self._score()

    def test_exceeding_what_the_job_asks_is_never_a_penalty(self) -> None:
        """Declining the over-qualified is a hiring decision (ADR-037). Golden
        candidate 1 has three years against a vacancy whose maximum is two."""
        assert self._score(job_min_years=1, candidate_years=25) == self._score()

    def test_an_unstated_figure_is_not_scored_as_zero(self) -> None:
        assert self._score(job_min_years=5, candidate_years=None) == self._score()

    def test_nothing_in_common_still_scores_zero(self) -> None:
        """Experience sits after the early return, so it cannot lift a candidate
        who shares no standard with the job off zero."""
        result = score_match(self.reqs, [], job_min_years=5, candidate_years=0)
        assert result.score == 0


# --------------------------------------------------------- Sprint 23: locality


class TestLocality:
    """Where a vacancy is orders equal scores. It never changes one."""

    @pytest.fixture
    async def world(self, db: AsyncSession) -> dict:
        karnataka = State(state_code=29, slug="karnataka-loc", name="Karnataka")
        tamil_nadu = State(state_code=33, slug="tamil-nadu-loc", name="Tamil Nadu")
        db.add_all([karnataka, tamil_nadu])
        await db.flush()
        bengaluru = District(district_code=572, name="BENGALURU URBAN", state_id=karnataka.id)
        mysuru = District(district_code=577, name="Mysuru", state_id=karnataka.id)
        chennai = District(district_code=603, name="Chennai", state_id=tamil_nadu.id)
        db.add_all([bengaluru, mysuru, chennai])

        standard = Skill(
            slug=f"loc-std-{uuid.uuid4().hex[:6]}",
            name="Retail billing",
            skill_type="technical",
            nsqf_level=Decimal("3"),
            nos_code=f"LOC/{uuid.uuid4().hex[:6]}",
            source="nsqf",
        )
        employer = Tenant(slug=f"loc-{uuid.uuid4().hex[:6]}", name="Store", tenant_type="employer")
        db.add_all([standard, employer])
        await db.flush()

        # Titles sort alphabetically in the *opposite* order to locality, so a
        # pass cannot come from the old title tie-break.
        jobs = {}
        for key, title, state, district in [
            ("far", "A cashier in Chennai", tamil_nadu, chennai),
            ("state", "B cashier in Mysuru", karnataka, mysuru),
            ("district", "C cashier in Bengaluru", karnataka, bengaluru),
        ]:
            job = Job(
                slug=f"{key}-{uuid.uuid4().hex[:6]}",
                tenant_id=employer.id,
                title=title,
                employment_type="full_time",
                status="published",
                state_id=state.id,
                district_id=district.id,
            )
            db.add(job)
            await db.flush()
            db.add(JobSkill(job_id=job.id, skill_id=standard.id, importance=3, is_mandatory=True))
            jobs[key] = job
        await db.commit()
        return {
            "standard": standard,
            "jobs": jobs,
            "karnataka": karnataka,
            "tamil_nadu": tamil_nadu,
        }

    async def _candidate(self, client: AsyncClient, world: dict, **location) -> dict:
        headers = await _auth(client)
        await client.post(
            "/me/profile/skills",
            headers=headers,
            json={"skill_slug": world["standard"].slug, "proficiency": 3},
        )
        if location:
            await client.put("/me/profile", headers=headers, json=location)
        return headers

    async def test_equal_scores_order_district_then_state_then_elsewhere(
        self, client: AsyncClient, world: dict
    ) -> None:
        headers = await self._candidate(
            client, world, location_state="Karnataka", location_district="Bengaluru"
        )
        items = (await client.get("/me/matches", headers=headers)).json()["items"]
        assert len({i["score"] for i in items}) == 1  # a tie, or this proves nothing
        assert [i["job"]["title"][0] for i in items] == ["C", "B", "A"]
        assert [i["locality"] for i in items] == [2, 1, 0]

    async def test_a_preferred_location_elsewhere_counts_as_local(
        self, client: AsyncClient, world: dict
    ) -> None:
        """Where someone lives and where they will work are different facts."""
        headers = await self._candidate(client, world, location_state="Karnataka")
        await client.post(
            "/me/profile/preferred_locations",
            headers=headers,
            json={"state": "Tamil Nadu", "district": "Chennai"},
        )
        items = (await client.get("/me/matches", headers=headers)).json()["items"]
        assert items[0]["job"]["title"].startswith("A")
        assert items[0]["locality"] == 2

    async def test_a_candidate_with_no_location_keeps_the_old_order(
        self, client: AsyncClient, world: dict
    ) -> None:
        headers = await self._candidate(client, world)
        items = (await client.get("/me/matches", headers=headers)).json()["items"]
        assert [i["job"]["title"][0] for i in items] == ["A", "B", "C"]
        assert {i["locality"] for i in items} == {0}

    async def test_the_state_filter_is_opt_in_and_works(
        self, client: AsyncClient, world: dict
    ) -> None:
        """`match_jobs` accepted `state_id` from Sprint 8 and nothing passed it."""
        headers = await self._candidate(client, world)
        everywhere = (await client.get("/me/matches", headers=headers)).json()["items"]
        assert len(everywhere) == 3
        only = (
            await client.get(
                "/me/matches", headers=headers, params={"state_id": str(world["tamil_nadu"].id)}
            )
        ).json()["items"]
        assert [i["job"]["title"][0] for i in only] == ["A"]
