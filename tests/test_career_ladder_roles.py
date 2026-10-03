"""`skills.roles_above` -- which roles build on one (Sprint 42, ADR-049).

The national data names no prerequisite between two roles, so a step is derived
and each rule below is one a reader would otherwise have to take on trust. Every
exclusion has a fixture where **that rule is the only reason** the row is out, so
deleting the rule fails exactly that test -- a fixture that is also excluded for
another reason proves nothing about this one.
"""

import itertools
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills import roles_above, search_roles
from api.modules.skills.concepts import SkillConcept
from api.modules.skills.hierarchy import (
    Occupation,
    QpNcoCode,
    QpSkill,
    QualificationPack,
    Sector,
)
from api.modules.skills.models import Skill

_n = itertools.count(1)


async def _sector(db: AsyncSession, name: str) -> Sector:
    i = next(_n)
    sector = Sector(sector_ref=f"lad-sec-{i}", name=name, slug=f"lad-sec-{i}")
    db.add(sector)
    await db.flush()
    return sector


async def _skill(db: AsyncSession, name: str, concept: SkillConcept | None = None) -> Skill:
    i = next(_n)
    skill = Skill(
        slug=f"lad-skill-{i}",
        name=name,
        skill_type="technical",
        nsqf_level=Decimal("4"),
        nos_code=f"LAD/N{i:04d}",
        source="nsqf",
        concept_id=concept.id if concept else None,
    )
    db.add(skill)
    await db.flush()
    return skill


async def _pack(
    db: AsyncSession,
    role: str,
    level: str | None,
    sector: Sector,
    standards: list[tuple[Skill, str]],
    *,
    code: str | None = None,
    current: bool = True,
    occupation: Occupation | None = None,
    nco: str | None = None,
) -> QualificationPack:
    i = next(_n)
    pack = QualificationPack(
        qp_code=code or f"LAD/Q{i:04d}",
        version="1.0",
        slug=f"lad-pack-{i}",
        name=f"{role} qualification",
        job_role=role,
        nsqf_level=Decimal(level) if level is not None else None,
        is_current=current,
        sector_id=sector.id,
        occupation_id=occupation.id if occupation else None,
    )
    db.add(pack)
    await db.flush()
    for skill, requirement in standards:
        db.add(QpSkill(qp_id=pack.id, skill_id=skill.id, requirement=requirement))
    if nco:
        db.add(QpNcoCode(qp_id=pack.id, nco_code=nco))
    await db.flush()
    return pack


@pytest.fixture
async def world(db: AsyncSession) -> dict:
    """An anchor at level 3 holding two specific standards, in a sector of its own."""
    sector = await _sector(db, "Healthcare")
    a, b = await _skill(db, "Assist patient care"), await _skill(db, "Measure vitals")
    anchor = await _pack(db, "Ward Assistant", "3", sector, [(a, "compulsory"), (b, "compulsory")])
    return {"sector": sector, "a": a, "b": b, "anchor": anchor}


async def _slugs(db: AsyncSession, anchor: QualificationPack) -> list[str]:
    ladder = await roles_above(db, anchor.slug)
    assert ladder is not None
    return [s.slug for s in ladder.steps]


async def test_a_higher_role_sharing_a_specific_standard_is_a_step(db, world) -> None:
    extra = await _skill(db, "Dress wounds")
    up = await _pack(
        db,
        "Senior Ward Assistant",
        "4",
        world["sector"],
        [(world["a"], "compulsory"), (extra, "compulsory")],
    )
    ladder = await roles_above(db, world["anchor"].slug)
    assert ladder is not None
    assert ladder.anchor.job_role == "Ward Assistant"
    assert [s.slug for s in ladder.steps] == [up.slug]
    step = ladder.steps[0]
    assert (step.shared_standards, step.compulsory_count) == (1, 2)
    assert step.nsqf_level == 4.0


async def test_the_same_or_a_lower_level_is_not_a_step(db, world) -> None:
    await _pack(db, "Peer Role", "3", world["sector"], [(world["a"], "compulsory")])
    await _pack(db, "Junior Role", "2", world["sector"], [(world["a"], "compulsory")])
    assert await _slugs(db, world["anchor"]) == []


async def test_the_rise_is_capped_at_two_levels(db, world) -> None:
    within = await _pack(db, "Two Up", "5", world["sector"], [(world["a"], "compulsory")])
    await _pack(db, "Half Past Two", "5.5", world["sector"], [(world["a"], "compulsory")])
    assert await _slugs(db, world["anchor"]) == [within.slug]


async def test_occupation_alone_is_not_grounds(db, world) -> None:
    """The case that put a Beauty Therapist after a Retail Sales Associate."""
    occupation = Occupation(
        occupation_ref="lad-occ", code="1", sector_id=world["sector"].id, name="X"
    )
    db.add(occupation)
    await db.flush()
    world["anchor"].occupation_id = occupation.id
    other = await _skill(db, "Unrelated unit")
    await _pack(
        db, "Same Occupation", "4", world["sector"], [(other, "compulsory")], occupation=occupation
    )
    assert await _slugs(db, world["anchor"]) == []


async def test_a_shared_nco_code_alone_is_not_grounds(db, world) -> None:
    await _pack(db, "Anchor Sibling", "3", world["sector"], [], nco="1111.0100")
    world["anchor"].job_role = "Ward Assistant"
    db.add(QpNcoCode(qp_id=world["anchor"].id, nco_code="1111.0100"))
    other = await _skill(db, "Unrelated unit")
    await _pack(db, "Same Nco", "4", world["sector"], [(other, "compulsory")], nco="1111.0100")
    assert await _slugs(db, world["anchor"]) == []


async def test_corroboration_is_reported_and_breaks_ties(db, world) -> None:
    occupation = Occupation(
        occupation_ref="lad-occ2", code="2", sector_id=world["sector"].id, name="Y"
    )
    db.add(occupation)
    await db.flush()
    world["anchor"].occupation_id = occupation.id
    db.add(QpNcoCode(qp_id=world["anchor"].id, nco_code="2222.0200"))
    filler1, filler2 = await _skill(db, "Filler one"), await _skill(db, "Filler two")
    plain = await _pack(
        db,
        "Plain Step",
        "4",
        world["sector"],
        [(world["a"], "compulsory"), (filler1, "compulsory")],
    )
    backed = await _pack(
        db,
        "Backed Step",
        "4",
        world["sector"],
        [(world["a"], "compulsory"), (filler2, "compulsory")],
        occupation=occupation,
        nco="2222.0200",
    )
    ladder = await roles_above(db, world["anchor"].slug)
    assert ladder is not None
    assert [s.slug for s in ladder.steps] == [backed.slug, plain.slug]
    assert (ladder.steps[0].same_occupation, ladder.steps[0].shared_nco) == (True, True)
    assert (ladder.steps[1].same_occupation, ladder.steps[1].shared_nco) == (False, False)


async def test_most_shared_ranks_ahead_of_the_nearest_rung(db, world) -> None:
    f1, f2 = await _skill(db, "Filler one"), await _skill(db, "Filler two")
    near = await _pack(  # level 3.5, 1 of 2 shared
        db, "Near Rung", "3.5", world["sector"], [(world["a"], "compulsory"), (f1, "compulsory")]
    )
    deep = await _pack(  # level 5, 2 of 2 shared
        db,
        "Deep Overlap",
        "5",
        world["sector"],
        [(world["a"], "compulsory"), (world["b"], "compulsory")],
    )
    assert await _slugs(db, world["anchor"]) == [deep.slug, near.slug]
    del f2


async def test_a_generic_standard_is_not_evidence(db, world) -> None:
    """Employability-style units sit in compulsory lists across many sectors; one
    of them in common is what 'led' a ward assistant to an automotive technician."""
    generic = await _skill(db, "Employability skills")
    for name in ("Retail", "Automotive"):  # with the anchor's sector, three in all
        await _pack(db, f"{name} Base", "3", await _sector(db, name), [(generic, "compulsory")])
    world["anchor"].qp_code = "LAD/ANCHOR"
    db.add(QpSkill(qp_id=world["anchor"].id, skill_id=generic.id, requirement="compulsory"))
    await _pack(
        db, "Generic Only", "4", await _sector(db, "Automotive 2"), [(generic, "compulsory")]
    )
    await db.flush()
    assert await _slugs(db, world["anchor"]) == []


async def test_a_standard_in_only_two_sectors_still_counts(db, world) -> None:
    """The boundary of the rule above: it takes three sectors to be generic."""
    shared = await _skill(db, "Dispense medication safely")
    db.add(QpSkill(qp_id=world["anchor"].id, skill_id=shared.id, requirement="compulsory"))
    other = await _sector(db, "Pharmacy")
    up = await _pack(db, "Pharmacy Assistant", "4", other, [(shared, "compulsory")])
    assert await _slugs(db, world["anchor"]) == [up.slug]


async def test_only_compulsory_standards_count(db, world) -> None:
    await _pack(db, "Elective Overlap", "4", world["sector"], [(world["a"], "elective")])
    skill = await _skill(db, "Own unit")
    await _pack(db, "Electives Only", "4", world["sector"], [(skill, "elective")])
    assert await _slugs(db, world["anchor"]) == []


async def test_a_standard_matches_at_concept_level(db, world) -> None:
    """Two rows for one standard -- the anchor's and the step's -- still meet."""
    concept = SkillConcept(slug=f"lad-concept-{next(_n)}", normalised_name="x", name="X")
    db.add(concept)
    await db.flush()
    mine = await _skill(db, "Handle linen (anchor's row)", concept)
    theirs = await _skill(db, "Handle linen (their row)", concept)
    db.add(QpSkill(qp_id=world["anchor"].id, skill_id=mine.id, requirement="compulsory"))
    up = await _pack(db, "Linen Supervisor", "4", world["sector"], [(theirs, "compulsory")])
    assert await _slugs(db, world["anchor"]) == [up.slug]


async def test_a_retired_pack_is_never_offered(db, world) -> None:
    await _pack(db, "Retired", "4", world["sector"], [(world["a"], "compulsory")], current=False)
    assert await _slugs(db, world["anchor"]) == []


async def test_variants_collapse_to_the_role_search_representative(db, world) -> None:
    """One row per role, and the pack picked is the one role search would pick --
    the rule lives in one place, and this is what holds the two callers to it."""
    base = await _pack(
        db, "Care Supervisor", "4", world["sector"], [(world["a"], "compulsory")], code="LAD/Q7000"
    )
    await _pack(
        db,
        "Care Supervisor",
        "4",
        world["sector"],
        [(world["a"], "compulsory")],
        code="LAD/Q7000-SI01",
    )
    ladder = await roles_above(db, world["anchor"].slug)
    assert ladder is not None and [s.slug for s in ladder.steps] == [base.slug]
    assert ladder.steps[0].variants == 2
    hits = await search_roles(db, "Care Supervisor")
    assert [h.slug for h in hits] == [base.slug]


async def test_divyangjan_packs_are_left_out_unless_the_anchor_is_one(db, world) -> None:
    await _pack(
        db, "Ward Supervisor (Divyangjan)", "4", world["sector"], [(world["a"], "compulsory")]
    )
    assert await _slugs(db, world["anchor"]) == []

    track = await _pack(
        db, "Ward Helper (Divyangjan)", "3", world["sector"], [(world["a"], "compulsory")]
    )
    up = await _pack(
        db, "Ward Lead (Divyangjan)", "4", world["sector"], [(world["a"], "compulsory")]
    )
    assert up.slug in await _slugs(db, track)


async def test_an_empty_ladder_is_not_an_unknown_role(db, world) -> None:
    ladder = await roles_above(db, world["anchor"].slug)
    assert ladder is not None and ladder.steps == []


async def test_an_unknown_retired_or_levelless_role_is_none(db, world) -> None:
    assert await roles_above(db, "no-such-role") is None
    retired = await _pack(db, "Retired Anchor", "3", world["sector"], [], current=False)
    levelless = await _pack(db, "No Level", None, world["sector"], [])
    assert await roles_above(db, retired.slug) is None
    assert await roles_above(db, levelless.slug) is None


async def test_the_result_is_capped(db, world) -> None:
    for i in range(10):
        await _pack(db, f"Step {i:02d}", "4", world["sector"], [(world["a"], "compulsory")])
    ladder = await roles_above(db, world["anchor"].slug, limit=50)
    assert ladder is not None and len(ladder.steps) == 8
    assert uuid.UUID(str(ladder.steps[0].qp_id))
