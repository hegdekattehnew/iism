"""nsqf hierarchy

Revision ID: a978e46b5272
Revises: 0007
Create Date: 2026-09-04 09:31:27.792884

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('occupations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name_en', sa.String(), nullable=False),
    sa.Column('name_hi', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_occupations_name_en'), 'occupations', ['name_en'], unique=True)
    op.create_table('sectors',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('sector_ref', sa.String(), nullable=False),
    sa.Column('name_en', sa.String(), nullable=False),
    sa.Column('name_hi', sa.String(), nullable=True),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sectors_sector_ref'), 'sectors', ['sector_ref'], unique=True)
    op.create_index(op.f('ix_sectors_slug'), 'sectors', ['slug'], unique=True)
    op.create_table('sub_sectors',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('sector_id', sa.Uuid(), nullable=False),
    sa.Column('sub_sector_ref', sa.String(), nullable=False),
    sa.Column('name_en', sa.String(), nullable=False),
    sa.Column('name_hi', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['sector_id'], ['sectors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sector_id', 'sub_sector_ref', name='uq_sub_sector_ref')
    )
    op.create_index('ix_sub_sectors_sector_id', 'sub_sectors', ['sector_id'], unique=False)
    op.create_table('qualification_packs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('qp_code', sa.String(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('name_en', sa.String(), nullable=False),
    sa.Column('name_hi', sa.String(), nullable=True),
    sa.Column('job_role_en', sa.String(), nullable=True),
    sa.Column('job_role_hi', sa.String(), nullable=True),
    sa.Column('nsqf_level', sa.Numeric(precision=3, scale=1), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('total_hours', sa.Integer(), nullable=True),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('sector_id', sa.Uuid(), nullable=True),
    sa.Column('sub_sector_id', sa.Uuid(), nullable=True),
    sa.Column('occupation_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('nsqf_level IS NULL OR (nsqf_level >= 1 AND nsqf_level <= 10)', name='ck_qp_nsqf_level'),
    sa.ForeignKeyConstraint(['occupation_id'], ['occupations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['sector_id'], ['sectors.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['sub_sector_id'], ['sub_sectors.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('qp_code', 'version', name='uq_qp_code_version')
    )
    op.create_index('ix_qp_current_level', 'qualification_packs', ['is_current', 'nsqf_level'], unique=False)
    op.create_index('ix_qp_sector_id', 'qualification_packs', ['sector_id'], unique=False)
    op.create_index(op.f('ix_qualification_packs_qp_code'), 'qualification_packs', ['qp_code'], unique=False)
    op.create_index(op.f('ix_qualification_packs_slug'), 'qualification_packs', ['slug'], unique=True)
    op.create_table('model_curricula',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('qp_code', sa.String(), nullable=False),
    sa.Column('mc_version', sa.String(), nullable=False),
    sa.Column('qp_id', sa.Uuid(), nullable=True),
    sa.Column('job_role_en', sa.String(), nullable=True),
    sa.Column('nsqf_level', sa.Numeric(precision=3, scale=1), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('total_minutes', sa.Integer(), nullable=True),
    sa.Column('document_ref', sa.String(length=1024), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['qp_id'], ['qualification_packs.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('qp_code', 'mc_version', name='uq_mc_code_version')
    )
    op.create_index(op.f('ix_model_curricula_qp_code'), 'model_curricula', ['qp_code'], unique=False)
    op.create_index('ix_model_curricula_qp_id', 'model_curricula', ['qp_id'], unique=False)
    op.create_table('qp_skills',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('qp_id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('requirement', sa.String(), nullable=False),
    sa.Column('group_name', sa.String(), nullable=True),
    sa.Column('nsqf_level', sa.Numeric(precision=3, scale=1), nullable=True),
    sa.CheckConstraint("requirement IN ('compulsory', 'elective', 'optional')", name='ck_qp_skill_requirement'),
    sa.ForeignKeyConstraint(['qp_id'], ['qualification_packs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('qp_id', 'skill_id', name='uq_qp_skill')
    )
    op.create_index('ix_qp_skills_qp_id', 'qp_skills', ['qp_id'], unique=False)
    op.create_index('ix_qp_skills_skill_id', 'qp_skills', ['skill_id'], unique=False)
    op.create_table('model_curriculum_skills',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('curriculum_id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('theory_minutes', sa.Integer(), nullable=True),
    sa.Column('practical_minutes', sa.Integer(), nullable=True),
    sa.Column('ojt_minutes', sa.Integer(), nullable=True),
    sa.Column('total_minutes', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['curriculum_id'], ['model_curricula.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('curriculum_id', 'skill_id', name='uq_mc_skill')
    )
    op.create_index('ix_mc_skills_skill_id', 'model_curriculum_skills', ['skill_id'], unique=False)
    op.add_column('skills', sa.Column('nos_code', sa.String(), nullable=True))
    op.add_column('skills', sa.Column('nos_version', sa.String(), nullable=True))
    op.add_column('skills', sa.Column('nos_type', sa.String(), nullable=True))
    # server_default is required: the column is NOT NULL and 52 curated skill
    # rows already exist. They are 'curated' by definition -- the NSQF import
    # sets 'nsqf' on everything it creates.
    op.add_column(
        "skills",
        sa.Column("source", sa.String(), nullable=False, server_default="curated"),
    )
    op.create_index(op.f('ix_skills_nos_code'), 'skills', ['nos_code'], unique=True)
    op.create_index('ix_skills_source', 'skills', ['source'], unique=False)
    op.create_check_constraint('ck_skills_source', 'skills', "source IN ('nsqf', 'curated')")


def downgrade() -> None:
    op.drop_constraint('ck_skills_source', 'skills', type_='check')
    op.drop_index('ix_skills_source', table_name='skills')
    op.drop_index(op.f('ix_skills_nos_code'), table_name='skills')
    op.drop_column('skills', 'source')
    op.drop_column('skills', 'nos_type')
    op.drop_column('skills', 'nos_version')
    op.drop_column('skills', 'nos_code')
    op.drop_index('ix_mc_skills_skill_id', table_name='model_curriculum_skills')
    op.drop_table('model_curriculum_skills')
    op.drop_index('ix_qp_skills_skill_id', table_name='qp_skills')
    op.drop_index('ix_qp_skills_qp_id', table_name='qp_skills')
    op.drop_table('qp_skills')
    op.drop_index('ix_model_curricula_qp_id', table_name='model_curricula')
    op.drop_index(op.f('ix_model_curricula_qp_code'), table_name='model_curricula')
    op.drop_table('model_curricula')
    op.drop_index(op.f('ix_qualification_packs_slug'), table_name='qualification_packs')
    op.drop_index(op.f('ix_qualification_packs_qp_code'), table_name='qualification_packs')
    op.drop_index('ix_qp_sector_id', table_name='qualification_packs')
    op.drop_index('ix_qp_current_level', table_name='qualification_packs')
    op.drop_table('qualification_packs')
    op.drop_index('ix_sub_sectors_sector_id', table_name='sub_sectors')
    op.drop_table('sub_sectors')
    op.drop_index(op.f('ix_sectors_slug'), table_name='sectors')
    op.drop_index(op.f('ix_sectors_sector_ref'), table_name='sectors')
    op.drop_table('sectors')
    op.drop_index(op.f('ix_occupations_name_en'), table_name='occupations')
    op.drop_table('occupations')
