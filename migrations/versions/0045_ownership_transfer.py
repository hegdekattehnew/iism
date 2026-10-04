"""Handing over an organisation as one act

Revision ID: 0045
Revises: 0044
Create Date: 2026-10-04

Sprint 44, BL-9.1. Two CHECK widenings, written by hand because **Alembic does
not diff CHECK constraint bodies**: a name added to `EVENT_NAMES` or `TEMPLATES`
alone is accepted by the model and rejected by the database, and here the
failing write is the transfer itself -- the notice is queued in the same
transaction as the role change, so a stale CHECK would refuse the whole handover
rather than lose one email.

* `analytics_events.name` gains `ownership_transferred`.
* `notifications.template` gains `ownership_received`.

Both value tuples are **frozen** here rather than imported: a migration
describes one moment, and importing the live tuple would make 0045 produce a
wider constraint the day a later sprint adds a name.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0045"
down_revision: str | None = "0044"
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
)
_EVENTS_ADDED = ("ownership_transferred",)

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
)
_TEMPLATES_ADDED = ("ownership_received",)


def upgrade() -> None:
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name",
        "analytics_events",
        one_of("name", _EVENTS_BEFORE + _EVENTS_ADDED),
    )
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template",
        "notifications",
        one_of("template", _TEMPLATES_BEFORE + _TEMPLATES_ADDED),
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template = 'ownership_received'")
    op.execute("DELETE FROM analytics_events WHERE name = 'ownership_transferred'")
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", _TEMPLATES_BEFORE)
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _EVENTS_BEFORE)
    )
