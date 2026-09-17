"""Widen the analytics event CHECK for applications

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-17

By hand, because **Alembic does not diff CHECK constraint bodies** -- the third
time this file pattern has been needed. A name added to `EVENT_NAMES` alone is
accepted by the model and rejected by the database, and `record()` swallows its
own failures by design, so the only symptom is events that silently never
appear.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "name IN ('matches_viewed', 'match_opened', 'gap_viewed', 'course_recommended', 'course_opened', 'employer_overview_viewed', 'employer_shortlist_viewed')"
_NEW = "name IN ('matches_viewed', 'match_opened', 'gap_viewed', 'course_recommended', 'course_opened', 'employer_overview_viewed', 'employer_shortlist_viewed', 'application_submitted', 'application_withdrawn', 'application_status_changed', 'job_saved')"


def upgrade() -> None:
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint("ck_analytics_event_name", "analytics_events", _NEW)


def downgrade() -> None:
    # Rows carrying a name the old constraint forbids would block the
    # narrowing, and an event nobody can record is not worth keeping.
    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('application_submitted', 'application_withdrawn', "
        "'application_status_changed', 'job_saved')"
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint("ck_analytics_event_name", "analytics_events", _OLD)
