"""`matching.score_against_roles` -- a candidate against a qualification (Sprint 42).

It must be the one scorer with a different list of requirements, never a second
scorer (ADR-037). The first test is the proof: build the same inputs by hand,
call `score_match` directly, and require the identical result.
"""

import itertools
from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateProfile, CandidateSkill
from api.modules.matching import score_against_roles, score_match
from api.modules.matching.scoring import HeldSkill, RequiredSkill
from api.modules.matching.service import attained_level, weights_from_settings
from api.modules.skills.hierarchy import QpEntryRoute, QpSkill, QualificationPack, Sector
from api.modules.skills.models import Skill

_n = itertools.count(1)


async def _skill(db: AsyncSession, name: str, level: str = "4") -> Skill:
    i = next(_n)
    skill = Skill(
        slug=f"rs-skill-{i}",
        name=name,
        skill_type="technical",
        nsqf_level=Decimal(level),
        nos_code=f"RS/N{i:04d}",
        source="nsqf",
    )
    db.add(skill)
    await db.flush()
    return skill


async def _pack(
    db: AsyncSession,
    standards: list[tuple[Skill, str]],
    *,
    level: str = "4",
    routes: list[tuple[str, str | None]] = (),  # type: ignore[assignment]
) -> QualificationPack:
    i = next(_n)
    sector = Sector(sector_ref=f"rs-sec-{i}", name="Healthcare", slug=f"rs-sec-{i}")
    db.add(sector)
    await db.flush()
    pack = QualificationPack(
        qp_code=f"RS/Q{i:04d}",
        version="1.0",
        slug=f"rs-pack-{i}",
        name="A role qualification",
        job_role=f"Role {i}",
        nsqf_level=Decimal(level),
        is_current=True,
        sector_id=sector.id,
    )
    db.add(pack)
    await db.flush()
    for skill, requirement in standards:
        db.add(
            QpSkill(
                qp_id=pack.id, skill_id=skill.id, requirement=requirement, nsqf_level=Decimal("4")
            )
        )
    for ordinal, (education, years) in enumerate(routes):
        db.add(
            QpEntryRoute(
                qp_id=pack.id,
                ordinal=ordinal,
                education_desc=education,
                experience_years=Decimal(years) if years is not None else None,
            )
        )
    await db.flush()
    return pack


async def _candidate(
    db: AsyncSession, holds: list[Skill], *, years: int = 2, source: str = "self_declared"
) -> CandidateProfile:
    user = User(phone=f"+9199{next(_n):08d}")
    db.add(user)
    await db.flush()
    profile = CandidateProfile(user_id=user.id, headline="rs", years_experience=years)
    db.add(profile)
    await db.flush()
    for skill in holds:
        db.add(
            CandidateSkill(profile_id=profile.id, skill_id=skill.id, proficiency=4, source=source)
        )
    await db.flush()
    return profile


async def test_it_is_the_one_scorer_with_a_different_list(db: AsyncSession) -> None:
    a, b, c = await _skill(db, "Unit A"), await _skill(db, "Unit B"), await _skill(db, "Unit C")
    pack = await _pack(db, [(a, "compulsory"), (b, "compulsory"), (c, "compulsory")])
    profile = await _candidate(db, [a, b], years=2)

    fit = (await score_against_roles(db, profile.id, [pack.id]))[pack.id]

    required = [
        RequiredSkill(
            skill_id=s.id,
            concept_id=s.concept_id,
            nos_code=s.nos_code,
            name=s.name,
            nsqf_level=Decimal("4"),
            importance=3,
            is_mandatory=True,
        )
        for s in sorted((a, b, c), key=lambda s: s.nos_code or "")
    ]
    held = [
        HeldSkill(
            skill_id=s.id, concept_id=None, name=s.name, proficiency=4, source="self_declared"
        )
        for s in (a, b)
    ]
    direct = score_match(
        required,
        held,
        job_level_min=Decimal("4"),
        candidate_level=attained_level(held, required),
        job_min_years=None,
        candidate_years=2,
        weights=weights_from_settings(),
    )
    assert fit.result == direct
    assert [m.name for m in fit.result.missing] == ["Unit C"]


async def test_electives_are_not_requirements(db: AsyncSession) -> None:
    a, elective = await _skill(db, "Core unit"), await _skill(db, "Optional unit")
    pack = await _pack(db, [(a, "compulsory"), (elective, "elective")])
    profile = await _candidate(db, [a])

    fit = (await score_against_roles(db, profile.id, [pack.id]))[pack.id]

    assert fit.result.missing == []
    assert fit.result.coverage == 1.0


async def test_a_missing_compulsory_standard_is_a_missing_mandatory_one(db) -> None:
    a, b = await _skill(db, "Held unit"), await _skill(db, "Lacking unit")
    pack = await _pack(db, [(a, "compulsory"), (b, "compulsory")])
    profile = await _candidate(db, [a])

    fit = (await score_against_roles(db, profile.id, [pack.id]))[pack.id]

    assert fit.result.missing_mandatory == 1
    assert fit.result.score <= 45


async def test_the_experience_floor_is_the_lowest_route_rounded_up(db) -> None:
    a = await _skill(db, "Unit")
    pack = await _pack(db, [(a, "compulsory")], routes=[("Grade 12", "3.0"), ("Diploma", "1.5")])
    short = await _candidate(db, [a], years=1)
    enough = await _candidate(db, [a], years=2)

    assert (await score_against_roles(db, short.id, [pack.id]))[pack.id].result.experience_shortfall
    met = (await score_against_roles(db, enough.id, [pack.id]))[pack.id]
    assert not met.result.experience_shortfall
    assert met.entry is not None
    assert met.entry.lowest_experience_years == Decimal("1.5")
    assert met.entry.education_options == ["Diploma", "Grade 12"]


async def test_no_entry_route_is_no_entry_answer_and_no_floor(db) -> None:
    a = await _skill(db, "Unit")
    pack = await _pack(db, [(a, "compulsory")])
    profile = await _candidate(db, [a], years=0)

    fit = (await score_against_roles(db, profile.id, [pack.id]))[pack.id]

    assert fit.entry is None
    assert not fit.result.experience_shortfall


async def test_nothing_in_nothing_out(db) -> None:
    profile = await _candidate(db, [])
    assert await score_against_roles(db, profile.id, []) == {}


@pytest.mark.parametrize("n_roles", [1, 5])
async def test_the_cost_does_not_grow_with_the_roles(db, n_roles) -> None:
    a = await _skill(db, "Shared unit")
    packs = [await _pack(db, [(a, "compulsory")]) for _ in range(5)][:n_roles]
    profile = await _candidate(db, [a])
    seen: list[str] = []

    def count(conn, cursor, statement, *args) -> None:  # type: ignore[no-untyped-def]
        seen.append(statement)

    connection = (await db.connection()).sync_connection
    event.listen(connection, "before_cursor_execute", count)
    try:
        await score_against_roles(db, profile.id, [p.id for p in packs])
    finally:
        event.remove(connection, "before_cursor_execute", count)

    # Held skills, the profile's four columns, its preferred locations, the packs, their
    # sector, their standards and their routes: seven reads however many roles are asked
    # about. (Six before Sprint 50: `candidate_facts` took the profile from the session when
    # it was already there, and fetched it with its seven eager collections when it was not.)
    assert len(seen) <= 7, f"{len(seen)} statements for {n_roles} role(s)"
