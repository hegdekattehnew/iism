"""marketplace: tenants, jobs, courses

Revision ID: 5bb899fa1e6c
Revises: 0002
Create Date: 2026-09-02 13:56:15.875673

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('tenants',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('tenant_type', sa.String(), nullable=False),
    sa.Column('city', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("tenant_type IN ('employer', 'course_provider')", name='ck_tenants_type'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenants_slug'), 'tenants', ['slug'], unique=True)
    op.create_table('courses',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('title_en', sa.String(), nullable=False),
    sa.Column('title_hi', sa.String(), nullable=True),
    sa.Column('description_en', sa.String(), nullable=True),
    sa.Column('description_hi', sa.String(), nullable=True),
    sa.Column('mode', sa.String(), nullable=False),
    sa.Column('language', sa.String(), nullable=False),
    sa.Column('duration_hours', sa.Integer(), nullable=True),
    sa.Column('fee_inr', sa.Integer(), nullable=True),
    sa.Column('nsqf_level', sa.Integer(), nullable=True),
    sa.Column('qualification_pack_code', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), sa.Computed("setweight(to_tsvector('english', coalesce(title_en, '')), 'A') || setweight(to_tsvector('simple',  coalesce(title_hi, '')), 'A') || setweight(to_tsvector('english', coalesce(description_en, '')), 'C') || setweight(to_tsvector('simple',  coalesce(description_hi, '')), 'C')", persisted=True), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("language IN ('en', 'hi', 'both')", name='ck_courses_language'),
    sa.CheckConstraint("mode IN ('online', 'offline', 'hybrid')", name='ck_courses_mode'),
    sa.CheckConstraint("status IN ('draft', 'published')", name='ck_courses_status'),
    sa.CheckConstraint('nsqf_level IS NULL OR (nsqf_level BETWEEN 1 AND 10)', name='ck_courses_nsqf_level'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_courses_slug'), 'courses', ['slug'], unique=True)
    op.create_index('ix_courses_status', 'courses', ['status'], unique=False)
    op.create_index('ix_courses_tenant_id', 'courses', ['tenant_id'], unique=False)
    op.create_table('jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('title_en', sa.String(), nullable=False),
    sa.Column('title_hi', sa.String(), nullable=True),
    sa.Column('description_en', sa.String(), nullable=True),
    sa.Column('description_hi', sa.String(), nullable=True),
    sa.Column('location_state', sa.String(), nullable=True),
    sa.Column('location_district', sa.String(), nullable=True),
    sa.Column('employment_type', sa.String(), nullable=False),
    sa.Column('experience_min_years', sa.Integer(), nullable=False),
    sa.Column('experience_max_years', sa.Integer(), nullable=True),
    sa.Column('salary_min_inr', sa.Integer(), nullable=True),
    sa.Column('salary_max_inr', sa.Integer(), nullable=True),
    sa.Column('nsqf_level_min', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), sa.Computed("setweight(to_tsvector('english', coalesce(title_en, '')), 'A') || setweight(to_tsvector('simple',  coalesce(title_hi, '')), 'A') || setweight(to_tsvector('english', coalesce(description_en, '')), 'C') || setweight(to_tsvector('simple',  coalesce(description_hi, '')), 'C')", persisted=True), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("employment_type IN ('full_time', 'part_time', 'contract', 'apprenticeship')", name='ck_jobs_employment_type'),
    sa.CheckConstraint("status IN ('draft', 'published')", name='ck_jobs_status'),
    sa.CheckConstraint('nsqf_level_min IS NULL OR (nsqf_level_min BETWEEN 1 AND 10)', name='ck_jobs_nsqf_level'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_slug'), 'jobs', ['slug'], unique=True)
    op.create_index('ix_jobs_status', 'jobs', ['status'], unique=False)
    op.create_index('ix_jobs_tenant_id', 'jobs', ['tenant_id'], unique=False)
    op.create_table('course_skills',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('level_taught', sa.Integer(), nullable=True),
    sa.CheckConstraint('level_taught IS NULL OR (level_taught BETWEEN 1 AND 10)', name='ck_course_skill_level'),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('course_id', 'skill_id', name='uq_course_skill')
    )
    op.create_index('ix_course_skills_skill_id', 'course_skills', ['skill_id'], unique=False)
    op.create_table('job_skills',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('job_id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('importance', sa.Integer(), nullable=False),
    sa.Column('is_mandatory', sa.Boolean(), nullable=False),
    sa.CheckConstraint('importance BETWEEN 1 AND 5', name='ck_job_skill_importance'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_id', 'skill_id', name='uq_job_skill')
    )
    op.create_index('ix_job_skills_skill_id', 'job_skills', ['skill_id'], unique=False)
    # Full-text indexes for the two new search_vector columns. Autogenerate
    # cannot infer these, so they are written by hand as in migration 0002.
    op.execute("CREATE INDEX ix_jobs_search_vector ON jobs USING GIN (search_vector)")
    op.execute(
        "CREATE INDEX ix_courses_search_vector ON courses USING GIN (search_vector)"
    )


def downgrade() -> None:
    # Migration 0002's trigram indexes are NOT touched here. Autogenerate wanted
    # to drop them in upgrade() and re-create them here; both were removed,
    # because they belong to 0002 and were never dropped in the first place.
    op.execute("DROP INDEX IF EXISTS ix_courses_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_jobs_search_vector")
    op.drop_index('ix_job_skills_skill_id', table_name='job_skills')
    op.drop_table('job_skills')
    op.drop_index('ix_course_skills_skill_id', table_name='course_skills')
    op.drop_table('course_skills')
    op.drop_index('ix_jobs_tenant_id', table_name='jobs')
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_index(op.f('ix_jobs_slug'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index('ix_courses_tenant_id', table_name='courses')
    op.drop_index('ix_courses_status', table_name='courses')
    op.drop_index(op.f('ix_courses_slug'), table_name='courses')
    op.drop_table('courses')
    op.drop_index(op.f('ix_tenants_slug'), table_name='tenants')
    op.drop_table('tenants')
