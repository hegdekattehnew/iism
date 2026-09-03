"""identity users and candidate profiles

Revision ID: 93a76c25852f
Revises: 0003
Create Date: 2026-09-02 14:17:19.523942

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Personal tenants back the candidate accounts created at first sign-in
    # (ADR-010). Alembic does not diff CHECK constraint bodies, so this is
    # written by hand — without it every candidate sign-in fails on insert.
    op.drop_constraint("ck_tenants_type", "tenants", type_="check")
    op.create_check_constraint(
        "ck_tenants_type",
        "tenants",
        "tenant_type IN ('employer', 'course_provider', 'personal')",
    )

    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('full_name', sa.String(), nullable=True),
    sa.Column('phone_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('preferred_locale', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('phone IS NOT NULL OR email IS NOT NULL', name='ck_users_has_identifier'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)
    op.create_table('candidate_profiles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('headline', sa.String(), nullable=True),
    sa.Column('location_state', sa.String(), nullable=True),
    sa.Column('location_district', sa.String(), nullable=True),
    sa.Column('years_experience', sa.Integer(), nullable=False),
    sa.Column('education_level', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('years_experience >= 0 AND years_experience <= 60', name='ck_candidate_experience'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_candidate_profiles_user_id'), 'candidate_profiles', ['user_id'], unique=True)
    op.create_table('memberships',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name='ck_membership_role'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'tenant_id', name='uq_membership_user_tenant')
    )
    op.create_index(op.f('ix_memberships_tenant_id'), 'memberships', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)
    op.create_table('candidate_skills',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('skill_id', sa.Uuid(), nullable=False),
    sa.Column('proficiency', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('self_declared', 'inferred', 'assessed', 'certified')", name='ck_candidate_skill_source'),
    sa.CheckConstraint('proficiency BETWEEN 1 AND 5', name='ck_candidate_skill_proficiency'),
    sa.ForeignKeyConstraint(['profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('profile_id', 'skill_id', name='uq_candidate_skill')
    )
    op.create_index('ix_candidate_skills_skill_id', 'candidate_skills', ['skill_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_candidate_skills_skill_id', table_name='candidate_skills')
    op.drop_table('candidate_skills')
    op.drop_index(op.f('ix_memberships_user_id'), table_name='memberships')
    op.drop_index(op.f('ix_memberships_tenant_id'), table_name='memberships')
    op.drop_table('memberships')
    op.drop_index(op.f('ix_candidate_profiles_user_id'), table_name='candidate_profiles')
    op.drop_table('candidate_profiles')
    op.drop_index(op.f('ix_users_phone'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    op.drop_constraint("ck_tenants_type", "tenants", type_="check")
    op.execute("DELETE FROM tenants WHERE tenant_type = 'personal'")
    op.create_check_constraint(
        "ck_tenants_type",
        "tenants",
        "tenant_type IN ('employer', 'course_provider')",
    )
