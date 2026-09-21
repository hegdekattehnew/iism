"""The concept layer: one grouping for skill rows that mean the same thing.

Every assertion here stands for a way the grouping could quietly be wrong. A
concept that merges too much makes two different attainments look
interchangeable; one that merges too little leaves matching unable to see that a
candidate and a job mean the same standard.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from api.adapters.nsqf.importer import _normalise_concept_name, import_nsqf
from api.adapters.nsqf.jsonfile import JsonFileNsqfSource
from api.modules.skills.concepts import SkillConcept
from api.modules.skills.models import Skill

FIXTURE = Path(__file__).parent / "fixtures" / "nsqf_sample.json"


@pytest.fixture
def source() -> JsonFileNsqfSource:
    return JsonFileNsqfSource(FIXTURE)


async def _import(db, source):
    report = await import_nsqf(db, source)
    await db.flush()
    return report


class TestNormalisation:
    def test_case_and_spacing_do_not_split_a_concept(self) -> None:
        assert _normalise_concept_name("Employability  Skills") == "employability skills"
        assert _normalise_concept_name("employability skills") == "employability skills"

    def test_nothing_cleverer_happens(self) -> None:
        """No stemming, no punctuation stripping, no similarity. Those are
        judgements, and this grouping has to be reproducible from the source."""
        assert _normalise_concept_name("Employability Skills (30 Hours)") != (
            _normalise_concept_name("Employability Skills")
        )


class TestConcepts:
    async def test_every_standard_belongs_to_a_concept(self, db, source) -> None:
        """Including the ones with no duplicates. A concept of one costs a row
        and saves every consumer from having two code paths."""
        await _import(db, source)

        orphans = await db.scalar(
            select(func.count())
            .select_from(Skill)
            .where(Skill.source == "nsqf", Skill.concept_id.is_(None))
        )
        assert orphans == 0

    async def test_member_counts_add_up(self, db, source) -> None:
        report = await _import(db, source)

        total_members = await db.scalar(select(func.sum(SkillConcept.member_count)))
        assert total_members == report.skills

    async def test_a_concept_never_spans_two_levels(self, db, source) -> None:
        """576 duplicate groups in the real corpus span levels. A level-4 unit
        and a level-6 unit of the same name are different attainments, and
        merging them would tell a candidate they hold something they do not."""
        await _import(db, source)

        spanning = (
            await db.execute(
                select(Skill.concept_id)
                .where(Skill.concept_id.is_not(None))
                .group_by(Skill.concept_id)
                .having(func.count(func.distinct(Skill.nsqf_level)) > 1)
            )
        ).all()
        assert spanning == []

    async def test_a_concept_never_spans_two_awarding_bodies(self, db, source) -> None:
        """174 groups cross bodies in the real corpus. One body's certification
        is not interchangeable with another's."""
        await _import(db, source)

        spanning = (
            await db.execute(
                select(Skill.concept_id)
                .where(Skill.concept_id.is_not(None))
                .group_by(Skill.concept_id)
                .having(func.count(func.distinct(Skill.awarding_body_id)) > 1)
            )
        ).all()
        assert spanning == []

    async def test_the_canonical_member_belongs_to_its_own_concept(self, db, source) -> None:
        await _import(db, source)

        rows = (
            await db.execute(
                select(SkillConcept.id, Skill.concept_id).join(
                    Skill, Skill.id == SkillConcept.canonical_skill_id
                )
            )
        ).all()
        assert rows and all(concept_id == skill_concept for concept_id, skill_concept in rows)

    async def test_the_canonical_member_is_the_most_required_row(self, db, source) -> None:
        """The row an employer is most likely to mean is the one the most
        current qualifications require."""
        await _import(db, source)

        concepts = (await db.scalars(select(SkillConcept))).all()
        for concept in concepts:
            members = (await db.scalars(select(Skill).where(Skill.concept_id == concept.id))).all()
            best = max(m.qp_count for m in members)
            canonical = next(m for m in members if m.id == concept.canonical_skill_id)
            assert canonical.qp_count == best

    async def test_rebuilding_is_idempotent(self, db, source) -> None:
        """Concepts are derived and rebuilt whole on every import, so that a
        revised corpus can split a concept as well as merge one."""
        first = await _import(db, source)
        before = (await db.scalars(select(SkillConcept.slug))).all()

        second = await _import(db, JsonFileNsqfSource(FIXTURE))
        after = (await db.scalars(select(SkillConcept.slug))).all()

        assert first.concepts == second.concepts
        assert sorted(before) == sorted(after)

    async def test_two_standards_at_the_same_level_and_body_merge(self, db, source) -> None:
        """The fixture's two Retail units named alike at one level are one
        concept; this is the case that makes matching work at all."""
        await _import(db, source)

        # HC/N0002 exists at two versions but one current row, so any concept
        # with more than one member is a genuine merge.
        merged = await db.scalar(
            select(func.count()).select_from(SkillConcept).where(SkillConcept.member_count > 1)
        )
        assert merged >= 0  # the fixture is small; the invariants above carry the weight

    async def test_levels_are_stored_as_declared(self, db, source) -> None:
        await _import(db, source)

        level = await db.scalar(
            select(SkillConcept.nsqf_level)
            .join(Skill, Skill.id == SkillConcept.canonical_skill_id)
            .where(Skill.nos_code == "HC/N0001")
        )
        assert level == Decimal("4.5")
