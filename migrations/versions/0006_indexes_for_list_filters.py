"""indexes for list filters

Revision ID: 301a6205dda9
Revises: 0005
Create Date: 2026-09-03 13:07:12.446774

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index('ix_courses_status_language', 'courses', ['status', 'language'], unique=False)
    op.create_index('ix_courses_status_mode', 'courses', ['status', 'mode'], unique=False)
    op.create_index('ix_jobs_status_employment', 'jobs', ['status', 'employment_type'], unique=False)
    op.create_index('ix_jobs_status_state', 'jobs', ['status', 'location_state'], unique=False)
    op.create_index('ix_skills_type_level', 'skills', ['skill_type', 'nsqf_level'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_skills_type_level', table_name='skills')
    op.drop_index('ix_jobs_status_state', table_name='jobs')
    op.drop_index('ix_jobs_status_employment', table_name='jobs')
    op.drop_index('ix_courses_status_mode', table_name='courses')
    op.drop_index('ix_courses_status_language', table_name='courses')
