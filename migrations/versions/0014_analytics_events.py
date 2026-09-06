"""Analytics events

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-06

ADR-025 defers the revenue model and makes measurement the substitute for a
price signal; nothing recorded anything until now, so any claim about
recommendation quality was an opinion.

It lands with matching rather than after it. A behavioural re-ranker (ADR-036)
can only be built on history already being collected, and the first weeks of a
scoring surface are exactly the data that cannot be gathered retrospectively.

`subject_id` is deliberately not a foreign key: an event about a job later
deleted is still a fact about what happened, and a cascade would quietly rewrite
history. `payload` carries ids and counts only -- ADR-023 excludes resume text,
Aadhaar and assessment results from analytics, and a free-form JSON column is
where such a thing would leak in.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('analytics_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('subject_type', sa.String(length=32), nullable=True),
    sa.Column('subject_id', sa.Uuid(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('occurred_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("name IN ('matches_viewed', 'match_opened', 'gap_viewed', 'course_recommended', 'course_opened')", name='ck_analytics_event_name'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_analytics_events_name_time', 'analytics_events', ['name', 'occurred_at'], unique=False)
    op.create_index(op.f('ix_analytics_events_occurred_at'), 'analytics_events', ['occurred_at'], unique=False)
    op.create_index('ix_analytics_events_user', 'analytics_events', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_analytics_events_user', table_name='analytics_events')
    op.drop_index(op.f('ix_analytics_events_occurred_at'), table_name='analytics_events')
    op.drop_index('ix_analytics_events_name_time', table_name='analytics_events')
    op.drop_table('analytics_events')
