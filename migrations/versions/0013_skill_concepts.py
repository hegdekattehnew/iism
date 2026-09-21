"""Skill concepts: one grouping for rows that mean the same thing

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-06

4,838 skill rows share a name with another row, and `Employability Skills` alone
is 67 rows across four awarding bodies and eight levels. Each is a separately
coded national standard so none can be removed, but a candidate declaring one
row and a job requiring another will never match -- they are different primary
keys, and scoring cannot repair that.

`skill_concepts` groups them. The rule is derived, never authored: same awarding
body + same normalised name + same NSQF level, which against the real corpus
gives 18,958 concepts from 21,303 rows.

Also widens `ck_skills_source` to admit `legacy`, the state the 52 curated
Sprint 2 skills move into once the marketplace is re-anchored. **Written by hand,
because Alembic does not diff CHECK constraint bodies** -- the project has been
caught by that three times now.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Invisible to --autogenerate: Alembic compares CHECK constraints by name,
    # never by body, so widening one has to be spelled out.
    op.drop_constraint("ck_skills_source", "skills", type_="check")
    op.create_check_constraint(
        "ck_skills_source", "skills", "source IN ('nsqf', 'curated', 'legacy')"
    )

    op.create_table('skill_concepts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('slug', sa.String(length=280), nullable=False),
    sa.Column('normalised_name', sa.Text(), nullable=False),
    sa.Column('name_en', sa.Text(), nullable=False),
    sa.Column('name_hi', sa.Text(), nullable=True),
    sa.Column('awarding_body_id', sa.Uuid(), nullable=True),
    sa.Column('nsqf_level', sa.Numeric(precision=3, scale=1), nullable=True),
    sa.Column('canonical_skill_id', sa.Uuid(), nullable=True),
    sa.Column('member_count', sa.Integer(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['awarding_body_id'], ['awarding_bodies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['canonical_skill_id'], ['skills.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('awarding_body_id', 'normalised_name', 'nsqf_level', name='uq_skill_concept_identity')
    )
    op.create_index('ix_skill_concepts_body', 'skill_concepts', ['awarding_body_id'], unique=False)
    op.create_index(op.f('ix_skill_concepts_slug'), 'skill_concepts', ['slug'], unique=True)
    op.add_column('skills', sa.Column('concept_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_skills_concept_id'), 'skills', ['concept_id'], unique=False)
    op.create_foreign_key('fk_skills_concept_id', 'skills', 'skill_concepts', ['concept_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # Any row already retired has to come back to 'curated' or the narrower
    # constraint cannot be applied.
    op.execute("UPDATE skills SET source = 'curated' WHERE source = 'legacy'")
    op.drop_constraint("ck_skills_source", "skills", type_="check")
    op.create_check_constraint("ck_skills_source", "skills", "source IN ('nsqf', 'curated')")

    op.drop_constraint('fk_skills_concept_id', 'skills', type_='foreignkey')
    op.drop_index(op.f('ix_skills_concept_id'), table_name='skills')
    op.drop_column('skills', 'concept_id')
    op.drop_index(op.f('ix_skill_concepts_slug'), table_name='skill_concepts')
    op.drop_index('ix_skill_concepts_body', table_name='skill_concepts')
    op.drop_table('skill_concepts')
