"""NSQF structure, entry routes, the content layer, and pruning

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-05

One coherent change to how the corpus is modelled; splitting it would leave the
schema briefly incoherent.

**Ownership.** `awarding_bodies` gives every qualification and standard an owner,
derived from its code prefix -- `LSC` owns `LSC/Q6101`. That resolves 99% of the
corpus, where the source's own `originSSC` field reaches 9%. Sector Skill
Councils and awarding bodies share the table because the source keeps them in one
collection under one key.

**Occupations** are rebuilt, keyed on `(sector_id, occupation_ref)`. Both the
code and the id are sector-local -- the id reuses "1", "2", "3" across forty-odd
sectors -- so keying on either alone collapses 1,811 occupations into 529. The
previous version of this table keyed on free text and had no stable identity.

**Entry routes.** `minEduQual` is a structured array of alternative ways in --
14,877 routes across 4,564 qualifications, each pairing an education requirement
with an experience requirement -- not the text description it was first taken
for. Modelled as rows because "can this candidate enrol?" is a query.

**Content.** Four tables, ~893,000 rows: what each standard actually says as
against what it is called. Every one keys on `(parent, ordinal)` rather than the
source's identifier, because `pcID` repeats within a unit in 17 of 6,000
standards sampled, `kpID` in 1 and `skillID` in 2 -- a natural key on the source
id fails partway through an import.

**Pruning.** `model_curriculum_skills` is dropped: it covered 424 of 1,950
curricula because 2,399 source entries carry a blank unitCode, so a twenty-unit
curriculum rendered as two, which misinforms rather than under-informs.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('awarding_bodies',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('body_ref', sa.String(length=32), nullable=True),
    sa.Column('name_en', sa.Text(), nullable=False),
    sa.Column('name_hi', sa.Text(), nullable=True),
    sa.Column('slug', sa.String(length=360), nullable=False),
    sa.Column('body_type', sa.String(length=32), nullable=False),
    sa.Column('logo_url', sa.String(length=1024), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("body_type IN ('sector_skill_council', 'awarding_body')", name='ck_awarding_body_type'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_awarding_bodies_code'), 'awarding_bodies', ['code'], unique=True)
    op.create_index(op.f('ix_awarding_bodies_slug'), 'awarding_bodies', ['slug'], unique=True)
    op.create_table('qp_entry_routes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('qp_id', sa.Uuid(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('education_ref', sa.String(length=32), nullable=True),
    sa.Column('education_desc', sa.Text(), nullable=True),
    sa.Column('education_specialisation', sa.Text(), nullable=True),
    sa.Column('experience_ref', sa.String(length=32), nullable=True),
    sa.Column('experience_desc', sa.String(length=64), nullable=True),
    sa.Column('experience_specialisation', sa.Text(), nullable=True),
    sa.Column('experience_years', sa.Numeric(precision=4, scale=1), nullable=True),
    sa.ForeignKeyConstraint(['qp_id'], ['qualification_packs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('qp_id', 'ordinal', name='uq_qp_entry_route_ordinal')
    )
    op.create_index('ix_qp_entry_routes_qp_id', 'qp_entry_routes', ['qp_id'], unique=False)
    op.create_table('qp_nco_codes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('qp_id', sa.Uuid(), nullable=False),
    sa.Column('nco_code', sa.String(length=32), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['qp_id'], ['qualification_packs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('qp_id', 'nco_code', name='uq_qp_nco_code')
    )
    op.create_index('ix_qp_nco_codes_nco_code', 'qp_nco_codes', ['nco_code'], unique=False)
    op.create_table('skill_generic_criteria',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('gs_ref', sa.String(length=32), nullable=True),
    sa.Column('text_en', sa.Text(), nullable=False),
    sa.Column('text_hi', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('skill_id', 'ordinal', name='uq_generic_criterion_ordinal')
    )
    op.create_index('ix_generic_criteria_skill_id', 'skill_generic_criteria', ['skill_id'], unique=False)
    op.create_table('skill_knowledge_params',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('kp_ref', sa.String(length=32), nullable=True),
    sa.Column('text_en', sa.Text(), nullable=False),
    sa.Column('text_hi', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('skill_id', 'ordinal', name='uq_knowledge_param_ordinal')
    )
    op.create_index('ix_knowledge_params_skill_id', 'skill_knowledge_params', ['skill_id'], unique=False)
    op.create_table('skill_performance_elements',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('name_en', sa.Text(), nullable=False),
    sa.Column('name_hi', sa.Text(), nullable=True),
    sa.Column('theory_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('practical_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('viva_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('ojt_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('total_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('skill_id', 'ordinal', name='uq_performance_element_ordinal')
    )
    op.create_index('ix_performance_elements_skill_id', 'skill_performance_elements', ['skill_id'], unique=False)
    op.create_table('skill_performance_criteria',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('element_id', sa.Uuid(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('pc_ref', sa.String(length=32), nullable=True),
    sa.Column('description_en', sa.Text(), nullable=False),
    sa.Column('description_hi', sa.Text(), nullable=True),
    sa.Column('theory_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('practical_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('viva_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('ojt_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('total_marks', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.ForeignKeyConstraint(['element_id'], ['skill_performance_elements.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('element_id', 'ordinal', name='uq_performance_criterion_ordinal')
    )
    op.create_index('ix_performance_criteria_element_id', 'skill_performance_criteria', ['element_id'], unique=False)
    op.drop_index(op.f('ix_mc_skills_skill_id'), table_name='model_curriculum_skills')
    op.drop_table('model_curriculum_skills')
    op.add_column('occupations', sa.Column('occupation_ref', sa.String(length=64), nullable=False))
    op.add_column('occupations', sa.Column('code', sa.String(length=16), nullable=True))
    op.add_column('occupations', sa.Column('sector_id', sa.Uuid(), nullable=False))
    op.alter_column('occupations', 'name_en',
               existing_type=sa.VARCHAR(),
               type_=sa.Text(),
               existing_nullable=False)
    op.alter_column('occupations', 'name_hi',
               existing_type=sa.VARCHAR(),
               type_=sa.Text(),
               existing_nullable=True)
    op.drop_index(op.f('ix_occupations_name_en'), table_name='occupations')
    op.create_index(op.f('ix_occupations_occupation_ref'), 'occupations', ['occupation_ref'], unique=False)
    op.create_index('ix_occupations_sector_id', 'occupations', ['sector_id'], unique=False)
    op.create_unique_constraint('uq_occupation_sector_ref', 'occupations', ['sector_id', 'occupation_ref'])
    op.create_foreign_key('fk_occupations_sector_id', 'occupations', 'sectors', ['sector_id'], ['id'], ondelete='CASCADE')
    op.add_column('qp_skills', sa.Column('weightage', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('qp_skills', sa.Column('total_marks', sa.Integer(), nullable=True))
    op.add_column('qualification_packs', sa.Column('awarding_body_id', sa.Uuid(), nullable=True))
    op.add_column('qualification_packs', sa.Column('total_marks', sa.Integer(), nullable=True))
    op.add_column('qualification_packs', sa.Column('min_pass_percent', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('qualification_packs', sa.Column('credits', sa.Numeric(precision=6, scale=2), nullable=True))
    op.create_index(op.f('ix_qualification_packs_awarding_body_id'), 'qualification_packs', ['awarding_body_id'], unique=False)
    op.create_index(op.f('ix_qualification_packs_occupation_id'), 'qualification_packs', ['occupation_id'], unique=False)
    op.create_foreign_key('fk_qualification_packs_awarding_body_id', 'qualification_packs', 'awarding_bodies', ['awarding_body_id'], ['id'], ondelete='SET NULL')
    op.add_column('sectors', sa.Column('sector_code', sa.String(length=32), nullable=True))
    op.add_column('sectors', sa.Column('logo_url', sa.String(length=1024), nullable=True))
    op.add_column('sectors', sa.Column('awarding_body_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_sectors_awarding_body_id'), 'sectors', ['awarding_body_id'], unique=False)
    op.create_index(op.f('ix_sectors_sector_code'), 'sectors', ['sector_code'], unique=False)
    op.create_foreign_key('fk_sectors_awarding_body_id', 'sectors', 'awarding_bodies', ['awarding_body_id'], ['id'], ondelete='SET NULL')
    op.add_column('skills', sa.Column('sector_id', sa.Uuid(), nullable=True))
    op.add_column('skills', sa.Column('occupation_id', sa.Uuid(), nullable=True))
    op.add_column('skills', sa.Column('awarding_body_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_skills_awarding_body_id'), 'skills', ['awarding_body_id'], unique=False)
    op.create_index(op.f('ix_skills_occupation_id'), 'skills', ['occupation_id'], unique=False)
    op.create_index(op.f('ix_skills_sector_id'), 'skills', ['sector_id'], unique=False)
    op.create_foreign_key('fk_skills_occupation_id', 'skills', 'occupations', ['occupation_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_skills_awarding_body_id', 'skills', 'awarding_bodies', ['awarding_body_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_skills_sector_id', 'skills', 'sectors', ['sector_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_skills_occupation_id', 'skills', type_='foreignkey')
    op.drop_constraint('fk_skills_awarding_body_id', 'skills', type_='foreignkey')
    op.drop_constraint('fk_skills_sector_id', 'skills', type_='foreignkey')
    op.drop_index(op.f('ix_skills_sector_id'), table_name='skills')
    op.drop_index(op.f('ix_skills_occupation_id'), table_name='skills')
    op.drop_index(op.f('ix_skills_awarding_body_id'), table_name='skills')
    op.drop_column('skills', 'awarding_body_id')
    op.drop_column('skills', 'occupation_id')
    op.drop_column('skills', 'sector_id')
    op.drop_constraint('fk_sectors_awarding_body_id', 'sectors', type_='foreignkey')
    op.drop_index(op.f('ix_sectors_sector_code'), table_name='sectors')
    op.drop_index(op.f('ix_sectors_awarding_body_id'), table_name='sectors')
    op.drop_column('sectors', 'awarding_body_id')
    op.drop_column('sectors', 'logo_url')
    op.drop_column('sectors', 'sector_code')
    op.drop_constraint('fk_qualification_packs_awarding_body_id', 'qualification_packs', type_='foreignkey')
    op.drop_index(op.f('ix_qualification_packs_occupation_id'), table_name='qualification_packs')
    op.drop_index(op.f('ix_qualification_packs_awarding_body_id'), table_name='qualification_packs')
    op.drop_column('qualification_packs', 'credits')
    op.drop_column('qualification_packs', 'min_pass_percent')
    op.drop_column('qualification_packs', 'total_marks')
    op.drop_column('qualification_packs', 'awarding_body_id')
    op.drop_column('qp_skills', 'total_marks')
    op.drop_column('qp_skills', 'weightage')
    op.drop_constraint('fk_occupations_sector_id', 'occupations', type_='foreignkey')
    op.drop_constraint('uq_occupation_sector_ref', 'occupations', type_='unique')
    op.drop_index('ix_occupations_sector_id', table_name='occupations')
    op.drop_index(op.f('ix_occupations_occupation_ref'), table_name='occupations')
    op.create_index(op.f('ix_occupations_name_en'), 'occupations', ['name_en'], unique=True)
    op.alter_column('occupations', 'name_hi',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(),
               existing_nullable=True)
    op.alter_column('occupations', 'name_en',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_column('occupations', 'sector_id')
    op.drop_column('occupations', 'code')
    op.drop_column('occupations', 'occupation_ref')
    op.create_table('model_curriculum_skills',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('curriculum_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('skill_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('theory_minutes', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('practical_minutes', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('ojt_minutes', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('total_minutes', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['curriculum_id'], ['model_curricula.id'], name=op.f('model_curriculum_skills_curriculum_id_fkey'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('model_curriculum_skills_skill_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('model_curriculum_skills_pkey')),
    sa.UniqueConstraint('curriculum_id', 'skill_id', name=op.f('uq_mc_skill'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('ix_mc_skills_skill_id'), 'model_curriculum_skills', ['skill_id'], unique=False)
    op.drop_index('ix_performance_criteria_element_id', table_name='skill_performance_criteria')
    op.drop_table('skill_performance_criteria')
    op.drop_index('ix_performance_elements_skill_id', table_name='skill_performance_elements')
    op.drop_table('skill_performance_elements')
    op.drop_index('ix_knowledge_params_skill_id', table_name='skill_knowledge_params')
    op.drop_table('skill_knowledge_params')
    op.drop_index('ix_generic_criteria_skill_id', table_name='skill_generic_criteria')
    op.drop_table('skill_generic_criteria')
    op.drop_index('ix_qp_nco_codes_nco_code', table_name='qp_nco_codes')
    op.drop_table('qp_nco_codes')
    op.drop_index('ix_qp_entry_routes_qp_id', table_name='qp_entry_routes')
    op.drop_table('qp_entry_routes')
    op.drop_index(op.f('ix_awarding_bodies_slug'), table_name='awarding_bodies')
    op.drop_index(op.f('ix_awarding_bodies_code'), table_name='awarding_bodies')
    op.drop_table('awarding_bodies')
