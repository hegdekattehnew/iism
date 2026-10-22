"""training centres: a child of the organisation that delivers training

Revision ID: 0059
Revises: 0058
Create Date: 2026-10-23

Sprint 95 (ADR-102, BL-18.3). A centre is a **child tenant** of an organisation that delivers
training: `tenants.parent_id` (a self foreign key, RESTRICT, so a parent cannot be deleted from under
its centres), an address, the place as written and the ids it resolved to, and `closed_at` (a centre
that no longer runs is closed, not deleted).

Three closed sets that Alembic does not diff are widened by hand, each list **frozen here** (a
migration describes one moment; importing the live tuple would make 0059 produce a wider constraint
the day a later sprint adds a name): the organisation types gain `training_centre`, the analytics
events gain three, and the notification templates gain two. `ck_tenants_centre_has_parent` is new:
a centre always has a parent and nothing else does, so "a centre of nobody" cannot be written.

Nothing is backfilled: no centre exists yet. The downgrade **deletes any centre that was created**
(and what points at it) before it removes the column, because a row of a type the older constraint
refuses cannot stay.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPES_BEFORE = ("employer", "course_provider", "personal")

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
)
_EVENTS_ADDED = ("centre_created", "centre_closed", "centres_bulk_uploaded")

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
)
_TEMPLATES_ADDED = ("centre_verified", "centre_verification_revoked")


def _widen(table: str, constraint: str, column: str, values: tuple[str, ...]) -> None:
    op.drop_constraint(constraint, table, type_="check")
    op.create_check_constraint(constraint, table, one_of(column, values))


def upgrade() -> None:
    op.add_column("tenants", sa.Column("parent_id", sa.Uuid(), nullable=True))
    op.add_column("tenants", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("location_state", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("location_district", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("state_id", sa.Uuid(), nullable=True))
    op.add_column("tenants", sa.Column("district_id", sa.Uuid(), nullable=True))
    op.add_column("tenants", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_tenants_parent_id", "tenants", "tenants", ["parent_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_tenants_state_id", "tenants", "states", ["state_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_tenants_district_id",
        "tenants",
        "districts",
        ["district_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tenants_parent_id", "tenants", ["parent_id"])
    _widen("tenants", "ck_tenants_type", "tenant_type", (*_TYPES_BEFORE, "training_centre"))
    op.create_check_constraint(
        "ck_tenants_centre_has_parent",
        "tenants",
        "(tenant_type = 'training_centre') = (parent_id IS NOT NULL)",
    )
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE + _EVENTS_ADDED)
    _widen(
        "notifications",
        "ck_notification_template",
        "template",
        _TEMPLATES_BEFORE + _TEMPLATES_ADDED,
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications WHERE template IN ('centre_verified', 'centre_verification_revoked')"
    )
    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('centre_created', 'centre_closed', 'centres_bulk_uploaded')"
    )
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE)
    _widen("analytics_events", "ck_analytics_event_name", "name", _EVENTS_BEFORE)
    # A centre is a row the older constraint refuses; what points at it goes first.
    op.execute(
        "DELETE FROM tenant_verification_events WHERE tenant_id IN "
        "(SELECT id FROM tenants WHERE tenant_type = 'training_centre')"
    )
    op.execute(
        "DELETE FROM notifications WHERE recipient_kind = 'tenant' AND recipient_id IN "
        "(SELECT id FROM tenants WHERE tenant_type = 'training_centre')"
    )
    op.execute("DELETE FROM tenants WHERE tenant_type = 'training_centre'")
    op.drop_constraint("ck_tenants_centre_has_parent", "tenants", type_="check")
    _widen("tenants", "ck_tenants_type", "tenant_type", _TYPES_BEFORE)
    op.drop_index("ix_tenants_parent_id", table_name="tenants")
    op.drop_constraint("fk_tenants_district_id", "tenants", type_="foreignkey")
    op.drop_constraint("fk_tenants_state_id", "tenants", type_="foreignkey")
    op.drop_constraint("fk_tenants_parent_id", "tenants", type_="foreignkey")
    for column in (
        "closed_at",
        "district_id",
        "state_id",
        "location_district",
        "location_state",
        "address",
        "parent_id",
    ):
        op.drop_column("tenants", column)
