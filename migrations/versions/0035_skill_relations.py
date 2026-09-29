"""A typed, weighted graph over skills

Revision ID: 0035
Revises: 0034
Create Date: 2026-09-27

Sprint 36, BL-6.1. `docs/scope-reconciliation.md` #7: typed `SkillRelation`
edges are named in `Skill`'s own Sprint 2 docstring as future work and were
never built. Foundation only -- no inference and no career-path output read
this table yet (BL-6.2/6.3, held for the next planning cycle); see
`api/modules/skills/graph.py`'s module docstring for why landing only this
much costs nothing to defer safely.

A new table, so the CHECK on `relation_type` needs no hand-written widening
the way an *existing* constraint would (Alembic does not diff CHECK bodies,
but there is nothing yet to diff against) -- it is simply generated from
`SKILL_RELATION_TYPES` at the moment this table is created.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SKILL_RELATION_TYPES = ("implies", "related_to")


def upgrade() -> None:
    op.create_table(
        "skill_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("from_skill_id", sa.Uuid(), nullable=False),
        sa.Column("to_skill_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relation_type IN (" + ", ".join(f"'{t}'" for t in SKILL_RELATION_TYPES) + ")",
            name="ck_skill_relation_type",
        ),
        sa.CheckConstraint("weight > 0 AND weight <= 1", name="ck_skill_relation_weight"),
        sa.CheckConstraint("from_skill_id != to_skill_id", name="ck_skill_relation_not_self"),
        sa.ForeignKeyConstraint(
            ["from_skill_id"], ["skills.id"], name="fk_skill_relations_from_skill", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["to_skill_id"], ["skills.id"], name="fk_skill_relations_to_skill", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_skill_id", "to_skill_id", "relation_type", name="uq_skill_relation_edge"
        ),
    )
    op.create_index(
        "ix_skill_relations_from_skill_id", "skill_relations", ["from_skill_id"]
    )
    op.create_index("ix_skill_relations_to_skill_id", "skill_relations", ["to_skill_id"])


def downgrade() -> None:
    op.drop_index("ix_skill_relations_to_skill_id", table_name="skill_relations")
    op.drop_index("ix_skill_relations_from_skill_id", table_name="skill_relations")
    op.drop_table("skill_relations")
