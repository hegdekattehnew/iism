"""Reports about listings, and an operator takedown

Revision ID: 0052
Revises: 0051
Create Date: 2026-10-13

Sprint 59 (BL-14.4, ADR-069). A table of what people said about a vacancy or course, two columns on
each listing that say an operator removed it, and the three closed sets that must grow with it. All
three are CHECK constraints Alembic does not diff, so each is widened by hand, and each list is
**frozen** here rather than imported: a migration describes one moment, and importing the live tuple
would make 0052 produce a wider constraint the day a later sprint adds a name.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from api.core.database import one_of

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TARGETS = ("job", "course")
_REASONS = (
    "asks_for_money",
    "fake_or_misleading",
    "discriminatory",
    "unsafe_or_illegal",
    "spam_or_duplicate",
    "other",
)
_STATUSES = ("open", "dismissed", "actioned")

_CLOSE_BEFORE = ("filled", "withdrawn", "expired")
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
)
_EVENTS_ADDED = (
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
)
_TEMPLATES_ADDED = ("listing_removed", "listing_restored")


def _widen(table: str, constraint: str, column: str, values: tuple[str, ...]) -> None:
    op.drop_constraint(constraint, table, type_="check")
    op.create_check_constraint(constraint, table, one_of(column, values))


def upgrade() -> None:
    op.create_table(
        "listing_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_slug", sa.String(), nullable=False),
        sa.Column("target_title", sa.String(), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL", name="fk_listing_reports_tenant"),
            nullable=True,
        ),
        sa.Column(
            "reporter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_listing_reports_reporter"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column(
            "handled_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_listing_reports_handled_by"),
            nullable=True,
        ),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "reporter_id", "target_type", "target_id", name="uq_listing_reports_reporter_target"
        ),
        sa.CheckConstraint(one_of("target_type", _TARGETS), name="ck_listing_reports_target"),
        sa.CheckConstraint(one_of("reason", _REASONS), name="ck_listing_reports_reason"),
        sa.CheckConstraint(one_of("status", _STATUSES), name="ck_listing_reports_status"),
        sa.CheckConstraint(
            "detail IS NULL OR length(detail) <= 1000", name="ck_listing_reports_detail"
        ),
        sa.CheckConstraint(
            "(status = 'open') = (handled_at IS NULL)", name="ck_listing_reports_handled"
        ),
    )
    op.create_index(
        "ix_listing_reports_target", "listing_reports", ["status", "target_type", "target_id"]
    )

    for table in ("jobs", "courses"):
        op.add_column(table, sa.Column("taken_down_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("takedown_reason", sa.Text(), nullable=True))
        op.create_check_constraint(
            f"ck_{table}_taken_down", table, "(taken_down_at IS NULL) = (takedown_reason IS NULL)"
        )

    # `nullable=True`: a NULL close reason is an open vacancy, as on the model.
    op.drop_constraint("ck_jobs_close_reason", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_close_reason",
        "jobs",
        one_of("close_reason", _CLOSE_BEFORE + ("taken_down",), nullable=True),
    )
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE + _EVENTS_ADDED)
    _widen(
        "notifications",
        "ck_notification_template",
        "template",
        _TEMPLATES_BEFORE + _TEMPLATES_ADDED,
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template IN ('listing_removed', 'listing_restored')")
    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('listing_reported', 'listing_reports_dismissed', 'listing_taken_down', 'listing_restored')"
    )
    # A taken-down vacancy was closed with a reason the old constraint does not know.
    op.execute("UPDATE jobs SET close_reason = 'withdrawn' WHERE close_reason = 'taken_down'")
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE)
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE)
    op.drop_constraint("ck_jobs_close_reason", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_close_reason", "jobs", one_of("close_reason", _CLOSE_BEFORE, nullable=True)
    )
    for table in ("courses", "jobs"):
        op.drop_constraint(f"ck_{table}_taken_down", table, type_="check")
        op.drop_column(table, "takedown_reason")
        op.drop_column(table, "taken_down_at")
    op.drop_index("ix_listing_reports_target", table_name="listing_reports")
    op.drop_table("listing_reports")
