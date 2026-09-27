"""Sprint 36, BL-6.1: the typed, weighted skill graph. Foundation only -- no
inference and no career-path output reads this table yet (BL-6.2/6.3),
so these tests are entirely about the model's own constraints, the same
shape `tests/test_enumerations.py` and the CHECK-constraint tests elsewhere
in this suite take for a table with no service layer yet.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills import SKILL_RELATION_TYPES, SkillRelation
from api.modules.skills.models import Skill


async def _skill(db: AsyncSession, slug: str) -> Skill:
    skill = Skill(slug=slug, name=slug.replace("-", " ").title(), skill_type="technical")
    db.add(skill)
    await db.flush()
    return skill


class TestSkillRelation:
    async def test_a_valid_edge_round_trips(self, db: AsyncSession) -> None:
        a = await _skill(db, "graph-a")
        b = await _skill(db, "graph-b")
        edge = SkillRelation(
            from_skill_id=a.id, to_skill_id=b.id, relation_type="implies", weight=0.8
        )
        db.add(edge)
        await db.commit()
        await db.refresh(edge)

        row = await db.get(SkillRelation, edge.id)
        assert row is not None
        assert row.from_skill_id == a.id
        assert row.to_skill_id == b.id
        assert row.relation_type == "implies"
        assert row.weight == 0.8

    async def test_both_named_relation_types_are_accepted(self, db: AsyncSession) -> None:
        assert set(SKILL_RELATION_TYPES) == {"implies", "related_to"}
        for relation_type in SKILL_RELATION_TYPES:
            a = await _skill(db, f"type-a-{relation_type}")
            b = await _skill(db, f"type-b-{relation_type}")
            db.add(SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type=relation_type))
        await db.commit()

    async def test_an_unknown_relation_type_is_refused_by_the_database(
        self, db: AsyncSession
    ) -> None:
        a = await _skill(db, "bad-type-a")
        b = await _skill(db, "bad-type-b")
        db.add(SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type="causes"))
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_a_skill_cannot_relate_to_itself(self, db: AsyncSession) -> None:
        a = await _skill(db, "self-edge")
        db.add(SkillRelation(from_skill_id=a.id, to_skill_id=a.id, relation_type="related_to"))
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_weight_must_be_positive_and_at_most_one(self, db: AsyncSession) -> None:
        a = await _skill(db, "weight-a")
        b = await _skill(db, "weight-b")
        db.add(
            SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type="implies", weight=0.0)
        )
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_weight_defaults_to_one(self, db: AsyncSession) -> None:
        a = await _skill(db, "weight-default-a")
        b = await _skill(db, "weight-default-b")
        edge = SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type="implies")
        db.add(edge)
        await db.commit()
        await db.refresh(edge)
        assert edge.weight == 1.0

    async def test_the_same_pair_and_type_cannot_be_duplicated(self, db: AsyncSession) -> None:
        a = await _skill(db, "dup-a")
        b = await _skill(db, "dup-b")
        db.add(SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type="related_to"))
        await db.commit()
        db.add(SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type="related_to"))
        with pytest.raises(IntegrityError):
            await db.commit()

    async def test_the_same_pair_may_carry_both_relation_types(self, db: AsyncSession) -> None:
        """Different claims about the same pair, not a duplicate of one."""
        a = await _skill(db, "both-types-a")
        b = await _skill(db, "both-types-b")
        db.add(SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type="implies"))
        db.add(SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type="related_to"))
        await db.commit()

    async def test_deleting_a_skill_cascades_to_its_edges(self, db: AsyncSession) -> None:
        a = await _skill(db, "cascade-a")
        b = await _skill(db, "cascade-b")
        edge = SkillRelation(from_skill_id=a.id, to_skill_id=b.id, relation_type="implies")
        db.add(edge)
        await db.commit()
        edge_id = edge.id

        await db.delete(a)
        await db.commit()
        # The FK cascade runs in the database; the session's identity map
        # does not know its cached `edge` was deleted server-side without
        # this (CLAUDE.md's own documented lesson, one table over).
        db.expire_all()
        assert await db.get(SkillRelation, edge_id) is None
