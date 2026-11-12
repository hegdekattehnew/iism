"""batch interests: a learner registers for a batch, and the centre marks who came

Revision ID: 0063
Revises: 0062
Create Date: 2026-10-24

Sprint 100 (ADR-103, BL-20.3, BL-18.7). `batch_interests` (0062) gains a fifth status, `attended`: the
centre's own report that an enrolled learner came, which takes a seat like `enrolled` does. Three
closed sets Alembic does not diff are widened by hand, each list **frozen here**: the batch interest
statuses, the analytics events (`batch_interest_registered`, `batch_interest_withdrawn`,
`batch_interest_status_changed`) and the notification templates (`batch_interest_registered`, an email
to the organisation; `batch_interest_status_changed`, an in-app notice to the learner).

Nothing is backfilled: nobody could register before this. The downgrade removes what the new names
wrote first (a status `attended` becomes `enrolled`, which is what it also was).
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUSES_BEFORE = ("registered", "withdrawn", "contacted", "enrolled")
_STATUSES_AFTER = (*_STATUSES_BEFORE, "attended")

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
    "applicants_exported",
    "enrolment_applied",
    "organisation_capability_changed",
    "centre_created",
    "centre_closed",
    "centres_bulk_uploaded",
    "delivery_requested",
    "delivery_invited",
    "delivery_approved",
    "delivery_ended",
    "batch_created",
    "batch_published",
    "batch_cancelled",
)
_EVENTS_ADDED = (
    "batch_interest_registered",
    "batch_interest_withdrawn",
    "batch_interest_status_changed",
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
    "application_status_message",
    "centre_verified",
    "centre_verification_revoked",
    "centre_manager_invitation",
    "delivery_requested",
    "delivery_invited",
    "delivery_approved",
    "delivery_declined",
    "delivery_revoked",
    "batch_cancelled",
)
_TEMPLATES_ADDED = ("batch_interest_registered", "batch_interest_status_changed")


def _widen(table: str, constraint: str, column: str, values: tuple[str, ...]) -> None:
    op.drop_constraint(constraint, table, type_="check")
    op.create_check_constraint(constraint, table, one_of(column, values))


def upgrade() -> None:
    _widen("batch_interests", "ck_batch_interest_status", "status", _STATUSES_AFTER)
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE + _EVENTS_ADDED)
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE + _TEMPLATES_ADDED)


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications WHERE template IN "
        "('batch_interest_registered', 'batch_interest_status_changed')"
    )
    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('batch_interest_registered', 'batch_interest_withdrawn', 'batch_interest_status_changed')"
    )
    op.execute("UPDATE batch_interests SET status = 'enrolled' WHERE status = 'attended'")
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE)
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE)
    _widen("batch_interests", "ck_batch_interest_status", "status", _STATUSES_BEFORE)
