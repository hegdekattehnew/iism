"""Retrieval ranks before it caps (Sprint 49, ADR-056).

The stage between "everything" and the scorer used to cut by an arbitrary key --
`Job.id` for a candidate, the UUID's text for a vacancy -- so once more than K rows
shared a standard, which K reached the scorer had nothing to do with fit. Measured
at 50,000 candidates and 5,000 vacancies, 2.8 and 2.2 of the true top twenty were
returned. These tests hold the rules that fix it, and the one that stops the fix
becoming a second scorer.

The suite's `db` fixture is one rolled-back transaction, which is fine here: nothing
in this file races.
"""

import json
import random
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.identity.models import Tenant, User
from api.modules.marketplace.models import (
    CandidateProfile,
    CandidateSkill,
    Job,
    JobSkill,
)
from api.modules.matching import employer as employer_module
from api.modules.matching import match_jobs
from api.modules.matching import service as service_module
from api.modules.matching.employer import _pool_held, _scarce_skills, candidates_for_job
from api.modules.matching.retrieval import bounded_candidates, bounded_jobs
from api.modules.matching.scoring import ScoreWeights, score_match
from api.modules.matching.service import (
    _held_skills,
    attained_level,
    requirements_for,
)
from api.modules.skills.concepts import SkillConcept
from api.modules.skills.models import Skill

SOURCES = ("certified", "assessed", "inferred", "self_declared")

# Two sets of weights, so the bound is checked against the cap rule as configured
# and not only as shipped.
WEIGHTINGS = {
    "default": ScoreWeights(),
    "retuned": ScoreWeights(
        coverage=0.5,
        level=0.2,
        experience=0.1,
        evidence_share=0.1,
        mandatory_gap_cap=0.3,
        min_coverage_for_cap=0.6,
        semantic=0.1,
    ),
}


def _skill(n: int, concept: SkillConcept | None = None) -> Skill:
    return Skill(
        slug=f"retrieval-skill-{n}",
        name=f"Standard {n}",
        skill_type="technical",
        nsqf_level=Decimal(2 + n % 5),
        nos_code=f"RTV/N{n:04d}",
        source="nsqf",
        concept_id=concept.id if concept else None,
    )


async def _employer(db: AsyncSession, slug: str = "retrieval-employer") -> Tenant:
    tenant = Tenant(slug=slug, name=slug, tenant_type="employer")
    db.add(tenant)
    await db.flush()
    return tenant


async def _candidate(
    db: AsyncSession,
    n: int,
    holds: list[tuple[Skill, str]],
    *,
    years: int = 2,
    profile_id: uuid.UUID | None = None,
) -> CandidateProfile:
    user = User(phone=f"+9198{n:08d}")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(
        id=profile_id or uuid.uuid4(), user_id=user.id, headline=f"c{n}", years_experience=years
    )
    db.add(profile)
    await db.flush()
    for skill, source in holds:
        db.add(
            CandidateSkill(profile_id=profile.id, skill_id=skill.id, proficiency=3, source=source)
        )
    await db.flush()
    return profile


async def _job(
    db: AsyncSession,
    tenant: Tenant,
    slug: str,
    needs: list[tuple[Skill, int, bool]],
    *,
    job_id: uuid.UUID | None = None,
    level: str | None = None,
    min_years: int | None = None,
) -> Job:
    job = Job(
        id=job_id or uuid.uuid4(),
        slug=slug,
        tenant_id=tenant.id,
        title=slug,
        employment_type="full_time",
        status="published",
        nsqf_level_min=Decimal(level) if level else None,
        experience_min_years=min_years,
    )
    db.add(job)
    await db.flush()
    for skill, importance, mandatory in needs:
        db.add(
            JobSkill(
                job_id=job.id, skill_id=skill.id, importance=importance, is_mandatory=mandatory
            )
        )
    await db.flush()
    return job


async def _random_world(
    db: AsyncSession, seed: int = 49
) -> tuple[list[Job], list[CandidateProfile]]:
    """A small marketplace with every complication the bound has to survive:
    two concepts each spanning two skill rows, mixed evidence, level floors,
    experience floors, mandatory and optional standards, and a vacancy that
    requires two rows of one concept."""
    rng = random.Random(seed)
    concepts = []
    for i in range(2):
        concept = SkillConcept(slug=f"rtv-concept-{i}", normalised_name=f"c{i}", name=f"C{i}")
        db.add(concept)
        concepts.append(concept)
    await db.flush()
    skills = [_skill(n, concepts[n // 2] if n < 4 else None) for n in range(10)]
    db.add_all(skills)
    await db.flush()

    tenant = await _employer(db)
    jobs = []
    for j in range(16):
        needs = [
            (s, rng.randint(1, 5), rng.random() < 0.4)
            for s in rng.sample(skills, rng.randint(2, 5))
        ]
        jobs.append(
            await _job(
                db,
                tenant,
                f"rtv-job-{j}",
                needs,
                level=rng.choice([None, "3", "5", "7"]),
                min_years=rng.choice([None, 0, 2, 5]),
            )
        )
    profiles = []
    for c in range(28):
        holds = [(s, rng.choice(SOURCES)) for s in rng.sample(skills, rng.randint(0, 7))]
        profiles.append(await _candidate(db, c, holds, years=rng.randint(0, 8)))
    return jobs, profiles


class TestTheBound:
    """The bound never undercuts the score, and no pair with a score is missing.

    "Undercut" allows for rounding: the integer score is `round(raw * 100)`, so it can
    exceed `bound * 100` by at most a half point.

    This is the guard that keeps the retrieval ranking from becoming a second
    scorer: it does not say the bound *equals* the score, it says it can never
    undercut it, so whatever the scorer would rank first is never cut for being
    ranked lower by something cruder.
    """

    @pytest.mark.parametrize("name", WEIGHTINGS)
    async def test_it_never_undercuts_the_score_vacancy_side(
        self, db: AsyncSession, name: str
    ) -> None:
        weights = WEIGHTINGS[name]
        jobs, profiles = await _random_world(db)
        requirements = await requirements_for(db, [j.id for j in jobs])
        held_by = await _pool_held(db, [p.id for p in profiles])
        bounds = {
            (row.job_id, row.profile_id): row.bound
            for row in (await db.execute(bounded_candidates([j.id for j in jobs], weights))).all()
        }

        scored = 0
        for job in jobs:
            reqs = requirements[job.id]
            for profile in profiles:
                held = held_by.get(profile.id, [])
                result = score_match(
                    reqs,
                    held,
                    job_level_min=job.nsqf_level_min,
                    candidate_level=attained_level(held, reqs),
                    job_min_years=job.experience_min_years,
                    candidate_years=profile.years_experience,
                    weights=weights,
                )
                key = (job.id, profile.id)
                if result.score > 0:
                    scored += 1
                    assert key in bounds, "a pair the scorer rates above zero was never retrieved"
                    assert result.score - 0.5 <= bounds[key] * 100 + 1e-6, (
                        f"bound {bounds[key]:.4f} below score {result.score}"
                    )
                else:
                    # Sharing a standard is the retrieval predicate; a zero score is
                    # exactly "shares none", so nothing outside the set was dropped.
                    assert not result.matched
        assert scored > 40, "the world is too thin to say anything"
        # ...and nothing was retrieved that the scorer finds nothing in common with.
        assert len(bounds) == scored

    @pytest.mark.parametrize("name", WEIGHTINGS)
    async def test_it_never_undercuts_the_score_candidate_side(
        self, db: AsyncSession, name: str
    ) -> None:
        weights = WEIGHTINGS[name]
        jobs, profiles = await _random_world(db, seed=7)
        requirements = await requirements_for(db, [j.id for j in jobs])

        checked = 0
        for profile in profiles:
            held = await _held_skills(db, profile.id)
            if not held:
                continue
            bounds = {
                row.job_id: row.bound
                for row in (await db.execute(bounded_jobs(held, state_id=None, weights=weights)))
            }
            for job in jobs:
                reqs = requirements[job.id]
                result = score_match(
                    reqs,
                    held,
                    job_level_min=job.nsqf_level_min,
                    candidate_level=attained_level(held, reqs),
                    job_min_years=job.experience_min_years,
                    candidate_years=profile.years_experience,
                    weights=weights,
                )
                if result.score > 0:
                    checked += 1
                    assert job.id in bounds
                    assert result.score - 0.5 <= bounds[job.id] * 100 + 1e-6
                else:
                    assert job.id not in bounds
        assert checked > 40

    async def test_the_cap_is_applied_to_the_bound_as_the_scorer_applies_it(
        self, db: AsyncSession
    ) -> None:
        """A candidate missing a mandatory standard is bounded by the cap, not by
        their coverage. Without this the bound would rank them level with someone
        eligible, and the best of the eligible would be cut for their sake."""
        skills = [_skill(n) for n in range(4)]
        db.add_all(skills)
        await db.flush()
        tenant = await _employer(db)
        job = await _job(
            db,
            tenant,
            "capped",
            [
                (skills[0], 5, False),
                (skills[1], 5, False),
                (skills[2], 5, False),
                (skills[3], 1, True),
            ],
        )
        eligible = await _candidate(db, 1, [(s, "certified") for s in skills])
        near = await _candidate(db, 2, [(s, "certified") for s in skills[:3]])
        weights = ScoreWeights()
        bounds = {
            row.profile_id: row.bound
            for row in (await db.execute(bounded_candidates([job.id], weights))).all()
        }
        assert bounds[eligible.id] > weights.mandatory_gap_cap
        assert bounds[near.id] == pytest.approx(weights.mandatory_gap_cap)

    async def test_it_is_tight_when_nothing_else_varies(self, db: AsyncSession) -> None:
        """An upper bound that is merely high would pass the test above while ranking
        badly. With evidence certified, the level floor met and experience met, the
        three components the bound assumes are full marks really are, so it must equal
        the score -- including for a candidate holding **two rows of one concept**, who
        must count once for the standard that concept satisfies, not twice."""
        concept = SkillConcept(slug="rtv-twin", normalised_name="twin", name="Twin")
        db.add(concept)
        await db.flush()
        twin_a, twin_b = _skill(0, concept), _skill(1, concept)
        other, gate = _skill(2), _skill(3)
        db.add_all([twin_a, twin_b, other, gate])
        await db.flush()
        tenant = await _employer(db)
        job = await _job(
            db,
            tenant,
            "tight",
            # Nothing mandatory: a mandatory gap would cap the score and hide a
            # double count behind the cap, which is the thing this test is for.
            [(twin_a, 4, False), (other, 2, False), (gate, 3, False)],
            level="2",
            min_years=1,
        )
        weights = ScoreWeights()
        holders = {
            "both twin rows": await _candidate(
                db, 1, [(twin_a, "certified"), (twin_b, "certified"), (other, "certified")]
            ),
            "everything": await _candidate(
                db,
                2,
                [(twin_b, "certified"), (other, "certified"), (gate, "certified")],
            ),
            "only the optional": await _candidate(db, 3, [(other, "certified")]),
        }
        requirements = (await requirements_for(db, [job.id]))[job.id]
        held_by = await _pool_held(db, [p.id for p in holders.values()])
        bounds = {
            row.profile_id: row.bound
            for row in (await db.execute(bounded_candidates([job.id], weights))).all()
        }
        for name, profile in holders.items():
            held = held_by[profile.id]
            result = score_match(
                requirements,
                held,
                job_level_min=job.nsqf_level_min,
                candidate_level=attained_level(held, requirements),
                job_min_years=job.experience_min_years,
                candidate_years=profile.years_experience,
                weights=weights,
            )
            assert bounds[profile.id] * 100 == pytest.approx(result.score, abs=0.5), name

    async def test_the_bound_reaches_no_response(self) -> None:
        """It ranks rows for loading and is never shown (ADR-036, ADR-037)."""
        from api.main import app

        schema = json.dumps(app.openapi())
        assert "retrieval_bound" not in schema
        assert '"bound"' not in schema


class TestTheCapKeepsTheBest:
    """With K lower than the number of sharers, the best must survive."""

    async def test_a_candidates_best_vacancy_survives_a_low_cap(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        skills = [_skill(n) for n in range(6)]
        db.add_all(skills)
        await db.flush()
        tenant = await _employer(db)
        # Twelve weak vacancies whose ids sort *before* the strong one: the old
        # `ORDER BY Job.id LIMIT 3` kept exactly these three and never saw it.
        for i in range(1, 13):
            await _job(
                db,
                tenant,
                f"weak-{i}",
                [(skills[0], 3, False)] + [(skills[3 + i % 3], 3, False)] * 1,
                job_id=uuid.UUID(int=i),
            )
        strong = await _job(
            db,
            tenant,
            "strong",
            [(skills[0], 3, False), (skills[1], 3, False), (skills[2], 3, False)],
            job_id=uuid.UUID(int=10**6),
        )
        candidate = await _candidate(db, 1, [(s, "certified") for s in skills[:3]])
        monkeypatch.setattr(service_module, "retrieval_limit", lambda: 3)

        ranked = await match_jobs(db, candidate.id, limit=3)

        assert ranked[0].job.id == strong.id
        assert len(ranked) == 3

    async def test_a_vacancys_best_candidate_survives_a_low_cap(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        skills = [_skill(n) for n in range(3)]
        db.add_all(skills)
        await db.flush()
        tenant = await _employer(db)
        job = await _job(
            db,
            tenant,
            "needs-three",
            [(skills[0], 3, False), (skills[1], 3, False), (skills[2], 3, True)],
        )
        # Twelve who hold one standard each, ids sorting *before* the strong
        # candidate's: the old `sorted(..., key=str)[:K]` kept these.
        for i in range(1, 13):
            await _candidate(db, i, [(skills[0], "certified")], profile_id=uuid.UUID(int=i))
        strong = await _candidate(
            db,
            99,
            [(s, "certified") for s in skills],
            profile_id=uuid.UUID(int=10**6),
        )
        monkeypatch.setattr(employer_module, "retrieval_limit", lambda: 3)

        ranked = await candidates_for_job(db, job)

        assert ranked[0].profile.id == strong.id
        assert len(ranked) == 3

    async def test_the_kept_set_is_exactly_the_highest_bounds(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every row outside the kept set has a bound no higher than any inside it,
        so no pair outside can score above the K-th bound."""
        jobs, profiles = await _random_world(db, seed=21)
        weights = ScoreWeights()
        every = {
            (row.job_id, row.profile_id): row.bound
            for row in (await db.execute(bounded_candidates([j.id for j in jobs], weights))).all()
        }
        from api.modules.matching.retrieval import best_candidates_for

        kept = await best_candidates_for(db, [j.id for j in jobs], limit=4, weights=weights)
        checked = 0
        for job in jobs:
            inside = {(job.id, pid) for pid in kept[job.id]}
            outside = {k for k in every if k[0] == job.id} - inside
            assert len(kept[job.id]) <= 4
            if outside:
                checked += 1
                assert min(every[k] for k in inside) >= max(every[k] for k in outside) - 1e-12
        assert checked >= 3, "the cap never bit; the test says nothing"

    async def test_equal_bounds_break_on_id_so_the_same_inputs_give_the_same_set(
        self, db: AsyncSession
    ) -> None:
        from api.modules.matching.retrieval import best_candidates_for

        skill = _skill(0)
        db.add(skill)
        await db.flush()
        tenant = await _employer(db)
        job = await _job(db, tenant, "tie", [(skill, 3, False)])
        ids = [uuid.UUID(int=n) for n in (9, 3, 7, 1, 5)]
        for n, pid in enumerate(ids):
            await _candidate(db, n, [(skill, "certified")], profile_id=pid)

        first = await best_candidates_for(db, [job.id], limit=3, weights=ScoreWeights())
        second = await best_candidates_for(db, [job.id], limit=3, weights=ScoreWeights())

        assert first[job.id] == second[job.id] == sorted(ids)[:3]


class TestNoParameterCeiling:
    async def test_held_skills_load_in_chunks(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """asyncpg refuses a statement with more than 32,767 bind parameters, and a
        pool is K per vacancy times the vacancies. The loader chunks; the answer must
        not depend on how."""
        skill = _skill(0)
        db.add(skill)
        await db.flush()
        profiles = [await _candidate(db, n, [(skill, "certified")]) for n in range(7)]
        ids = [p.id for p in profiles]
        whole = await _pool_held(db, ids)

        monkeypatch.setattr(employer_module, "_IN_CHUNK", 2)
        chunked = await _pool_held(db, ids)

        assert set(chunked) == set(ids)
        assert {k: [h.skill_id for h in v] for k, v in chunked.items()} == {
            k: [h.skill_id for h in v] for k, v in whole.items()
        }

    async def test_a_pool_past_the_ceiling_is_loaded(self, db: AsyncSession) -> None:
        """The failure was 40,000 ids in one `IN`. No row is needed to prove the
        statement is no longer built that way: forty thousand ids that match
        nothing must be accepted."""
        out = await _pool_held(db, [uuid.uuid4() for _ in range(40_000)])
        assert out == {}


class TestScarceSkillsStillRankExactly:
    async def test_held_counts_decide_a_tie_at_the_cutoff(self, db: AsyncSession) -> None:
        """Holders are only counted for standards tied with the last one that can make
        the list. The ones that tie must still be ordered by supply -- and a standard
        asked for less often must not appear because supply was never counted for it."""
        names = "ABCDFGE"
        skills = {name: _skill(i) for i, name in enumerate(names)}
        for name, skill in skills.items():
            skill.name = name
        db.add_all(skills.values())
        await db.flush()
        tenant = await _employer(db)
        demand = {"A": 3, "B": 2, "C": 2, "D": 2, "F": 2, "G": 2, "E": 1}
        for name, count in demand.items():
            for n in range(count):
                await _job(db, tenant, f"scarce-{name}-{n}", [(skills[name], 3, False)])
        supply = {"A": 0, "B": 5, "C": 1, "D": 3, "F": 4, "G": 2, "E": 0}
        n = 0
        for name, holders in supply.items():
            for _ in range(holders):
                n += 1
                await _candidate(db, n, [(skills[name], "certified")])

        # A is the most demanded; of the five asked for twice, the least supplied come
        # next. E (asked for once) is never a contender.
        two = await _scarce_skills(db, tenant_id=tenant.id, limit=2)
        three = await _scarce_skills(db, tenant_id=tenant.id, limit=3)
        everything = await _scarce_skills(db, tenant_id=tenant.id, limit=10)

        assert [s.name for s in two] == ["A", "C"]
        assert [s.name for s in three] == ["A", "C", "G"]
        assert [s.name for s in everything] == ["A", "C", "G", "D", "F", "B", "E"]
        assert {s.name: s.held_by for s in everything} == supply
