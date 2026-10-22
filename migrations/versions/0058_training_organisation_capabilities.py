"""what a training organisation does, and what it says about itself

Revision ID: 0058
Revises: 0057
Create Date: 2026-10-22

Sprint 94 (ADR-102, BL-18.13 and BL-18.14).

`tenants.publishes_courses` and `tenants.delivers_training` are the two capabilities of one training
organisation: it may sell courses, deliver training at centres, or both. They are plain booleans, not
two organisation types, because splitting one real organisation into two tenants would split its
verification, staff and history (ADR-038). **Backfilled**: every existing `course_provider` publishes
courses (that is all a provider could do) and none delivers; every other organisation has neither.

`year_established`, `affiliations` and `teaching_languages` are what an organisation says about
itself, shown as its own claim. Nothing is backfilled: they start empty.

`organisation_capability_changed` joins the analytics event names. The CHECK on that column is one
Alembic does not diff, so it is widened by hand with the list **frozen here**: a migration describes
one moment, and importing the live tuple would make 0058 produce a wider constraint the day a later
sprint adds a name.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0058"
down_revision: str | None = "0057"
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
    "applicants_exported",
    "enrolment_applied",
)


def _widen(values: tuple[str, ...]) -> None:
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", values)
    )


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "publishes_courses", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "delivers_training", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column("tenants", sa.Column("year_established", sa.Integer(), nullable=True))
    op.add_column("tenants", sa.Column("affiliations", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("teaching_languages", sa.Text(), nullable=True))
    # Every provider that exists sells courses: it was the only thing a provider could do.
    op.execute("UPDATE tenants SET publishes_courses = true WHERE tenant_type = 'course_provider'")
    _widen(_EVENTS_BEFORE + ("organisation_capability_changed",))


def downgrade() -> None:
    op.execute("DELETE FROM analytics_events WHERE name = 'organisation_capability_changed'")
    _widen(_EVENTS_BEFORE)
    op.drop_column("tenants", "teaching_languages")
    op.drop_column("tenants", "affiliations")
    op.drop_column("tenants", "year_established")
    op.drop_column("tenants", "delivers_training")
    op.drop_column("tenants", "publishes_courses")
