"""Matching: the scoring rules, and the endpoints that expose them.

The scorer is pure, so most of this needs no database at all — which is the
point of keeping it that way. Every case here is a rule someone could
plausibly weaken later without noticing.
"""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from api.modules.analytics.models import AnalyticsEvent
from api.modules.matching.scoring import (
    MANDATORY_GAP_CAP,
    HeldSkill,
    RequiredSkill,
    score_match,
)


def _req(name: str, *, importance: int = 3, mandatory: bool = False, concept=None, level=None):
    return RequiredSkill(
        skill_id=uuid.uuid4(),
        concept_id=concept,
        nos_code=f"X/{name}",
        name_en=name,
        nsqf_level=level,
        importance=importance,
        is_mandatory=mandatory,
    )


def _held(req: RequiredSkill, *, source: str = "certified", proficiency: int = 4):
    """A candidate holding exactly the given requirement."""
    return HeldSkill(
        skill_id=req.skill_id,
        concept_id=req.concept_id,
        name_en=req.name_en,
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
            name_en="standard, another issue of it",
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
            name_en="something else",
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

        assert [m.name_en for m in result.missing] == [
            "mandatory",
            "optional-high",
            "optional-low",
        ]


async def _auth(client: AsyncClient) -> dict[str, str]:
    """Same shape as tests/test_profile.py, so sign-in behaves identically."""
    phone = "9" + uuid.uuid4().int.__str__()[:9]
    code = (await client.post("/auth/otp/request", json={"phone": phone})).json()["debug_code"]
    body = (await client.post("/auth/otp/verify", json={"phone": phone, "code": code})).json()
    return {"authorization": f"Bearer {body['access_token']}"}


class TestMatchEndpoints:
    async def test_matches_require_authentication(self, client) -> None:
        assert (await client.get("/me/matches")).status_code == 401

    async def test_a_profile_with_no_skills_says_so(self, db, client) -> None:
        """Not "no matches found": zero declared skills is a different state,
        and the difference is a dead end versus a next step."""
        headers = await _auth(client)
        await client.get("/me/profile", headers=headers)  # creates the profile
        body = (await client.get("/me/matches", headers=headers)).json()

        assert body["has_skills"] is False
        assert body["items"] == []

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
