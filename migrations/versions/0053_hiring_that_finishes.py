"""A message with a status change, private notes on an applicant, and the CSV that goes with them

Revision ID: 0053
Revises: 0052
Create Date: 2026-10-13

Sprint 60 (BL-14.7, BL-14.8, ADR-070). Four nullable columns on `applications`, each free text
bounded by a CHECK as well as by the schema, and two closed sets widened by hand: the analytics
event written when an employer exports applicants, and the notification template for a status
change that carries a message. Both lists are **frozen** here rather than imported: a migration
describes one moment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0053"
down_revision: str | None = "0052"
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
    "career_ladder_viewed",
    "ownership_transferred",
    "jobs_bulk_uploaded",
    "courses_bulk_uploaded",
    "listing_reported",
    "listing_reports_dismissed",
    "listing_taken_down",
    "listing_restored",
)
_TEMPLATES_BEFORE = (
    "application_received",
    "application_status_changed",
    "course_interest_registered",
    "organisation_invitation",
    "job_alert",
    "vacancy_closed",
    "course_interest_status_changed",
    "sponsor_offer",
    "organisation_verified",
    "organisation_verification_revoked",
    "ownership_received",
    "grievance_update",
    "listing_removed",
    "listing_restored",
)


def _widen(table: str, constraint: str, column: str, values: tuple[str, ...]) -> None:
    op.drop_constraint(constraint, table, type_="check")
    op.create_check_constraint(constraint, table, one_of(column, values))


def upgrade() -> None:
    op.add_column("applications", sa.Column("status_message", sa.Text(), nullable=True))
    op.add_column(
        "applications", sa.Column("status_message_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("applications", sa.Column("employer_notes", sa.Text(), nullable=True))
    op.add_column(
        "applications", sa.Column("employer_notes_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_application_status_message",
        "applications",
        "status_message IS NULL OR length(status_message) <= 500",
    )
    op.create_check_constraint(
        "ck_application_employer_notes",
        "applications",
        "employer_notes IS NULL OR length(employer_notes) <= 2000",
    )
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE + ("applicants_exported",))
    _widen(
        "notifications",
        "ck_notification_template",
        "template",
        _TEMPLATES_BEFORE + ("application_status_message",),
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template = 'application_status_message'")
    op.execute("DELETE FROM analytics_events WHERE name = 'applicants_exported'")
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE)
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE)
    op.drop_constraint("ck_application_employer_notes", "applications", type_="check")
    op.drop_constraint("ck_application_status_message", "applications", type_="check")
    for column in ("employer_notes_at", "employer_notes", "status_message_at", "status_message"):
        op.drop_column("applications", column)
