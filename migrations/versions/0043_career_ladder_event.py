"""A candidate may look at the roles that build on theirs

Revision ID: 0043
Revises: 0042
Create Date: 2026-10-03

Sprint 42, career ladders (ADR-049). The feature stores nothing -- a ladder is
derived at read time from the qualification data -- so the only schema change is
the one event that measures it: `career_ladder_viewed`.

Hand-written for the reason these always are: **Alembic does not diff CHECK
constraint bodies**, so a name added to `EVENT_NAMES` alone is accepted by the
model and rejected by the database, and `record()` swallows its own failures --
the only symptom would be events that silently never appear. The value tuple is
**frozen** rather than imported: a migration describes one moment.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EVENTS_BEFORE = (
    "matches_viewed",
    "match_opened",
    "gap_viewed",
    "course_recommended",
    "course_opened",
    "employer_overview_viewed",
    "employer_shortlist_viewed",
    "application_submitted",
    "application_withdrawn",
    "application_status_changed",
    "job_saved",
    "role_suggested",
    "skills_bulk_added",
    "course_interest_registered",
    "course_interest_withdrawn",
    "course_interest_status_changed",
    "member_invited",
    "member_invitation_accepted",
    "member_removed",
    "member_role_changed",
    "job_closed",
    "job_reopened",
    "job_alerts_sent",
    "course_dismissed",
    "application_review_submitted",
    "sponsor_intent_recorded",
)
_EVENTS_ADDED = ("career_ladder_viewed",)


def upgrade() -> None:
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name",
        "analytics_events",
        one_of("name", _EVENTS_BEFORE + _EVENTS_ADDED),
    )


def downgrade() -> None:
    op.execute("DELETE FROM analytics_events WHERE name = 'career_ladder_viewed'")
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _EVENTS_BEFORE)
    )
