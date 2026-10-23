"""delivering somebody else's course: the arrangement between a seller and a partner

Revision ID: 0061
Revises: 0060
Create Date: 2026-10-23

Sprint 97 (ADR-102, ADR-103, BL-18.15). `course_delivery_authorisations` is the one table: the
organisation that sells (`provider_id`), the one that would deliver (`partner_id`), the scope
(`course_id`, NULL for every course the seller has) and the timestamps from which the state is
**derived**, never stored: requested, approved, declined, revoked. Two partial unique indexes keep
one open row per (provider, partner, scope), and are the arbiter of a double tap.

Two closed sets Alembic does not diff are widened by hand, each list **frozen here**: the analytics
events gain four (`delivery_requested`, `delivery_invited`, `delivery_approved`, `delivery_ended`)
and the notification templates gain five (`delivery_requested`, `delivery_invited`,
`delivery_approved`, `delivery_declined`, `delivery_revoked`).

Nothing is backfilled: no arrangement exists yet. The downgrade drops the table and the queued
notices and events of the new names first, because a row of a name the older constraint refuses
cannot stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0061"
down_revision: str | None = "0060"
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
)
_EVENTS_ADDED = ("delivery_requested", "delivery_invited", "delivery_approved", "delivery_ended")

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
)
_TEMPLATES_ADDED = (
    "delivery_requested",
    "delivery_invited",
    "delivery_approved",
    "delivery_declined",
    "delivery_revoked",
)


def _widen(table: str, constraint: str, column: str, values: tuple[str, ...]) -> None:
    op.drop_constraint(constraint, table, type_="check")
    op.create_check_constraint(constraint, table, one_of(column, values))


def upgrade() -> None:
    op.create_table(
        "course_delivery_authorisations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=True),
        sa.Column("initiated_by", sa.String(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by_side", sa.String(), nullable=True),
        sa.Column("ended_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint(one_of("initiated_by", ("provider", "partner")), name="ck_delivery_initiated_by"),
        sa.CheckConstraint(
            "ended_by_side IS NULL OR ended_by_side IN ('provider', 'partner')",
            name="ck_delivery_ended_by_side",
        ),
        sa.CheckConstraint("(ended_at IS NULL) = (ended_by_side IS NULL)", name="ck_delivery_ended_pair"),
        sa.CheckConstraint("provider_id <> partner_id", name="ck_delivery_two_organisations"),
        sa.ForeignKeyConstraint(["provider_id"], ["tenants.id"], name="fk_delivery_provider_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_id"], ["tenants.id"], name="fk_delivery_partner_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name="fk_delivery_course_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], name="fk_delivery_requested_by", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], name="fk_delivery_approved_by", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ended_by"], ["users.id"], name="fk_delivery_ended_by", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delivery_provider_id", "course_delivery_authorisations", ["provider_id"])
    op.create_index("ix_delivery_partner_id", "course_delivery_authorisations", ["partner_id"])
    op.create_index(
        "uq_delivery_open_all",
        "course_delivery_authorisations",
        ["provider_id", "partner_id"],
        unique=True,
        postgresql_where=sa.text("course_id IS NULL AND ended_at IS NULL"),
    )
    op.create_index(
        "uq_delivery_open_course",
        "course_delivery_authorisations",
        ["provider_id", "partner_id", "course_id"],
        unique=True,
        postgresql_where=sa.text("course_id IS NOT NULL AND ended_at IS NULL"),
    )
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE + _EVENTS_ADDED)
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE + _TEMPLATES_ADDED)


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications WHERE template IN "
        "('delivery_requested', 'delivery_invited', 'delivery_approved', "
        "'delivery_declined', 'delivery_revoked')"
    )
    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('delivery_requested', 'delivery_invited', 'delivery_approved', 'delivery_ended')"
    )
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE)
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE)
    op.drop_index("uq_delivery_open_course", table_name="course_delivery_authorisations")
    op.drop_index("uq_delivery_open_all", table_name="course_delivery_authorisations")
    op.drop_index("ix_delivery_partner_id", table_name="course_delivery_authorisations")
    op.drop_index("ix_delivery_provider_id", table_name="course_delivery_authorisations")
    op.drop_table("course_delivery_authorisations")
