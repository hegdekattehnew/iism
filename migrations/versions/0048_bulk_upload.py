"""A reference an organisation can give its own listings, and two events

Revision ID: 0048
Revises: 0047
Create Date: 2026-10-05

Sprint 51, BL-14 (ADR-063): bulk upload of vacancies and courses.

* `jobs.external_ref` and `courses.external_ref`, nullable, with a **partial unique index per
  organisation** (`(tenant_id, external_ref) WHERE external_ref IS NOT NULL`). A corrected file
  is re-uploaded whole, so the rows that already exist must be recognised and skipped rather than
  duplicated; the organisation's own id for a listing is the one key that is exact. Two
  organisations may use the same reference.
* `analytics_events.name` gains `jobs_bulk_uploaded` and `courses_bulk_uploaded`. Written by hand
  because **Alembic does not diff CHECK constraint bodies**, and the value tuple is **frozen**
  here: a migration describes one moment.

No data change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0048"
down_revision: str | None = "0047"
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
)
_EVENTS_ADDED = ("jobs_bulk_uploaded", "courses_bulk_uploaded")


def upgrade() -> None:
    op.add_column("jobs", sa.Column("external_ref", sa.String(), nullable=True))
    op.add_column("courses", sa.Column("external_ref", sa.String(), nullable=True))
    op.create_index(
        "uq_jobs_tenant_external_ref",
        "jobs",
        ["tenant_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )
    op.create_index(
        "uq_courses_tenant_external_ref",
        "courses",
        ["tenant_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name",
        "analytics_events",
        one_of("name", _EVENTS_BEFORE + _EVENTS_ADDED),
    )


def downgrade() -> None:
    op.execute("DELETE FROM analytics_events WHERE name IN ('jobs_bulk_uploaded', 'courses_bulk_uploaded')")
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _EVENTS_BEFORE)
    )
    op.drop_index("uq_courses_tenant_external_ref", table_name="courses")
    op.drop_index("uq_jobs_tenant_external_ref", table_name="jobs")
    op.drop_column("courses", "external_ref")
    op.drop_column("jobs", "external_ref")
