"""batches: one run of one course at one centre, and the learners who registered for it

Revision ID: 0062
Revises: 0061
Create Date: 2026-10-23

Sprint 98 (ADR-103, BL-18.5). Two tables. `batches` is a run of a course at a centre: the course,
the centre (a child tenant), the dates, the seats, the mode, an optional label, schedule and fee
override, and the **three** things a person decides (`status`: draft, published, cancelled) with
why and when it was cancelled. Open, full, running and finished are **derived** from the dates, the
seats and the learners enrolled, never stored. `batch_interests` is a learner's interest in a
batch, shaped like `course_interests` and written by nothing yet (registration is Sprint 100); it
exists so seats and the cancellation notice have something to count.

Two closed sets Alembic does not diff are widened by hand, each list **frozen here**: the analytics
events gain three (`batch_created`, `batch_published`, `batch_cancelled`) and the notification
templates gain one (`batch_cancelled`).

Nothing is backfilled: no batch exists yet. The downgrade removes the queued notices and events of
the new names first, because a row of a name the older constraint refuses cannot stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0062"
down_revision: str | None = "0061"
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
    "organisation_capability_changed",
    "centre_created",
    "centre_closed",
    "centres_bulk_uploaded",
    "delivery_requested",
    "delivery_invited",
    "delivery_approved",
    "delivery_ended",
)
_EVENTS_ADDED = ("batch_created", "batch_published", "batch_cancelled")

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
)
_TEMPLATES_ADDED = ("batch_cancelled",)

_STATUSES = ("draft", "published", "cancelled")
_MODES = ("in_person", "hybrid", "online")
_REASONS = ("by_organisation", "arrangement_ended", "course_unavailable", "centre_closed")
_INTEREST = ("registered", "withdrawn", "contacted", "enrolled")


def _widen(table: str, constraint: str, column: str, values: tuple[str, ...]) -> None:
    op.drop_constraint(constraint, table, type_="check")
    op.create_check_constraint(constraint, table, one_of(column, values))


def upgrade() -> None:
    op.create_table(
        "batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("centre_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("schedule", sa.String(), nullable=True),
        sa.Column("fee_inr", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(one_of("status", _STATUSES), name="ck_batches_status"),
        sa.CheckConstraint(one_of("mode", _MODES), name="ck_batches_mode"),
        sa.CheckConstraint(
            "cancel_reason IS NULL OR " + one_of("cancel_reason", _REASONS),
            name="ck_batches_cancel_reason",
        ),
        sa.CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL)",
            name="ck_batches_cancelled_pair",
        ),
        sa.CheckConstraint("seats >= 1 AND seats <= 5000", name="ck_batches_seats"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_batches_dates"),
        sa.CheckConstraint("fee_inr IS NULL OR fee_inr >= 0", name="ck_batches_fee"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name="fk_batches_course_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["centre_id"], ["tenants.id"], name="fk_batches_centre_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_batches_created_by", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_batches_centre_id", "batches", ["centre_id"])
    op.create_index("ix_batches_course_id", "batches", ["course_id"])
    op.create_index("ix_batches_status_starts", "batches", ["status", "starts_on"])
    op.create_table(
        "batch_interests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("contact_shared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(one_of("status", _INTEREST), name="ck_batch_interest_status"),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["batches.id"], name="fk_batch_interests_batch_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name="fk_batch_interests_profile_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "profile_id", name="uq_batch_interest_batch_profile"),
    )
    op.create_index("ix_batch_interests_batch_id", "batch_interests", ["batch_id"])
    op.create_index("ix_batch_interests_profile_id", "batch_interests", ["profile_id"])
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE + _EVENTS_ADDED)
    _widen(
        "notifications",
        "ck_notification_template",
        "template",
        _TEMPLATES_BEFORE + _TEMPLATES_ADDED,
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template = 'batch_cancelled'")
    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('batch_created', 'batch_published', 'batch_cancelled')"
    )
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE)
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE)
    op.drop_index("ix_batch_interests_profile_id", table_name="batch_interests")
    op.drop_index("ix_batch_interests_batch_id", table_name="batch_interests")
    op.drop_table("batch_interests")
    op.drop_index("ix_batches_status_starts", table_name="batches")
    op.drop_index("ix_batches_course_id", table_name="batches")
    op.drop_index("ix_batches_centre_id", table_name="batches")
    op.drop_table("batches")
