"""Widen the analytics event CHECK for the employer console

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-07

Written by hand, because **Alembic does not diff CHECK constraint bodies**.
Adding a name to `EVENT_NAMES` is invisible to autogenerate, so the model would
accept the new events and the database would reject them -- and `record()`
swallows its own failures by design, so the only symptom would be events
silently never appearing.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = (
    "name IN ('matches_viewed', 'match_opened', 'gap_viewed', "
    "'course_recommended', 'course_opened')"
)
_NEW = (
    "name IN ('matches_viewed', 'match_opened', 'gap_viewed', "
    "'course_recommended', 'course_opened', 'employer_overview_viewed', "
    "'employer_shortlist_viewed')"
)


def upgrade() -> None:
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint("ck_analytics_event_name", "analytics_events", _NEW)


def downgrade() -> None:
    # Rows carrying a name the old constraint forbids would block the narrowing,
    # and an event nobody can record is not worth keeping.
    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('employer_overview_viewed', 'employer_shortlist_viewed')"
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint("ck_analytics_event_name", "analytics_events", _OLD)
