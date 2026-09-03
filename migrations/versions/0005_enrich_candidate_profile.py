"""enrich candidate profile

Revision ID: e187382be7da
Revises: 0004
Create Date: 2026-09-03 12:36:02.095684

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('candidate_certifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('issuing_body', sa.String(), nullable=True),
    sa.Column('credential_id', sa.String(), nullable=True),
    sa.Column('issued_on', sa.Date(), nullable=True),
    sa.Column('expires_on', sa.Date(), nullable=True),
    sa.Column('nsqf_level', sa.Integer(), nullable=True),
    sa.Column('skill_id', sa.Uuid(), nullable=True),
    sa.CheckConstraint('expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on', name='ck_certification_dates'),
    sa.ForeignKeyConstraint(['profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_candidate_certifications_profile_id', 'candidate_certifications', ['profile_id'], unique=False)
    op.create_table('candidate_educations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('qualification', sa.String(), nullable=False),
    sa.Column('institution', sa.String(), nullable=True),
    sa.Column('specialisation', sa.String(), nullable=True),
    sa.Column('education_level', sa.String(), nullable=True),
    sa.Column('year_completed', sa.Integer(), nullable=True),
    sa.Column('is_pursuing', sa.Boolean(), nullable=False),
    sa.CheckConstraint('year_completed IS NULL OR (year_completed BETWEEN 1950 AND 2100)', name='ck_education_year'),
    sa.ForeignKeyConstraint(['profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_candidate_educations_profile_id', 'candidate_educations', ['profile_id'], unique=False)
    op.create_table('candidate_experiences',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('employer_name', sa.String(), nullable=False),
    sa.Column('role_title', sa.String(), nullable=False),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('started_on', sa.Date(), nullable=False),
    sa.Column('ended_on', sa.Date(), nullable=True),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.CheckConstraint('ended_on IS NULL OR ended_on >= started_on', name='ck_experience_dates'),
    sa.CheckConstraint('is_current = false OR ended_on IS NULL', name='ck_experience_current'),
    sa.ForeignKeyConstraint(['profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_candidate_experiences_profile_id', 'candidate_experiences', ['profile_id'], unique=False)
    op.create_table('candidate_languages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('language', sa.String(), nullable=False),
    sa.Column('proficiency', sa.String(), nullable=False),
    sa.Column('can_read', sa.Boolean(), nullable=False),
    sa.Column('can_write', sa.Boolean(), nullable=False),
    sa.CheckConstraint("proficiency IN ('basic', 'conversational', 'fluent', 'native')", name='ck_language_proficiency'),
    sa.ForeignKeyConstraint(['profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('profile_id', 'language', name='uq_candidate_language')
    )
    op.create_index('ix_candidate_languages_profile_id', 'candidate_languages', ['profile_id'], unique=False)
    op.create_table('candidate_preferred_locations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('state', sa.String(), nullable=False),
    sa.Column('district', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('profile_id', 'state', 'district', name='uq_candidate_preferred_location')
    )
    op.create_index('ix_candidate_preferred_locations_profile_id', 'candidate_preferred_locations', ['profile_id'], unique=False)
    op.create_table('candidate_preferred_roles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('profile_id', 'title', name='uq_candidate_preferred_role')
    )
    op.create_index('ix_candidate_preferred_roles_profile_id', 'candidate_preferred_roles', ['profile_id'], unique=False)
    op.add_column('candidate_profiles', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('candidate_profiles', sa.Column('gender', sa.String(), nullable=True))
    # server_default is required: the column is NOT NULL and existing profile
    # rows have no value for it.
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "willing_to_relocate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column('candidate_profiles', sa.Column('preferred_employment_type', sa.String(), nullable=True))
    op.add_column('candidate_profiles', sa.Column('expected_salary_min_inr', sa.Integer(), nullable=True))
    op.add_column('candidate_profiles', sa.Column('expected_salary_max_inr', sa.Integer(), nullable=True))
    op.add_column('candidate_profiles', sa.Column('notice_period', sa.String(), nullable=True))
    op.add_column('candidate_profiles', sa.Column('onboarding_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint('ck_candidate_gender', 'candidate_profiles', "gender IS NULL OR gender IN ('female', 'male', 'other', 'prefer_not_to_say')")
    op.create_check_constraint('ck_candidate_notice', 'candidate_profiles', "notice_period IS NULL OR notice_period IN ('immediate', 'within_15_days', 'within_30_days', 'over_30_days')")
    op.create_check_constraint('ck_candidate_salary_range', 'candidate_profiles', 'expected_salary_min_inr IS NULL OR expected_salary_max_inr IS NULL OR expected_salary_max_inr >= expected_salary_min_inr')


def downgrade() -> None:
    op.drop_constraint('ck_candidate_salary_range', 'candidate_profiles', type_='check')
    op.drop_constraint('ck_candidate_notice', 'candidate_profiles', type_='check')
    op.drop_constraint('ck_candidate_gender', 'candidate_profiles', type_='check')
    op.drop_column('candidate_profiles', 'onboarding_completed_at')
    op.drop_column('candidate_profiles', 'notice_period')
    op.drop_column('candidate_profiles', 'expected_salary_max_inr')
    op.drop_column('candidate_profiles', 'expected_salary_min_inr')
    op.drop_column('candidate_profiles', 'preferred_employment_type')
    op.drop_column('candidate_profiles', 'willing_to_relocate')
    op.drop_column('candidate_profiles', 'gender')
    op.drop_column('candidate_profiles', 'date_of_birth')
    op.drop_index('ix_candidate_preferred_roles_profile_id', table_name='candidate_preferred_roles')
    op.drop_table('candidate_preferred_roles')
    op.drop_index('ix_candidate_preferred_locations_profile_id', table_name='candidate_preferred_locations')
    op.drop_table('candidate_preferred_locations')
    op.drop_index('ix_candidate_languages_profile_id', table_name='candidate_languages')
    op.drop_table('candidate_languages')
    op.drop_index('ix_candidate_experiences_profile_id', table_name='candidate_experiences')
    op.drop_table('candidate_experiences')
    op.drop_index('ix_candidate_educations_profile_id', table_name='candidate_educations')
    op.drop_table('candidate_educations')
    op.drop_index('ix_candidate_certifications_profile_id', table_name='candidate_certifications')
    op.drop_table('candidate_certifications')
