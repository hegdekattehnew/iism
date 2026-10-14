"""An operator's enrolment of an agency's file, and who attested the notice was read out

Revision ID: 0054
Revises: 0053
Create Date: 2026-10-14

Sprint 61 (BL-14.10, ADR-071). Two tables and one widened closed set.

`enrolment_batches` is the record of the act: the programme tag, the file's name, four counts, and
the operator who attested that the privacy notice was read out to everyone in the file, with the
notice version. `enrolment_batch_members` says which batch put each person in a programme; it lives
on this side (pointing at `candidate_profiles`) because `marketplace` cannot import `operations`.

The analytics event list is **frozen** here rather than imported: a migration describes one moment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from api.core.database import one_of

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OUTCOMES = ("created", "tagged")
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
)


def _widen(values: tuple[str, ...]) -> None:
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", values)
    )


def upgrade() -> None:
    op.create_table(
        "enrolment_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("programme", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_enrolment_batches_actor"),
            nullable=True,
        ),
        sa.Column("attested_notice_version", sa.Text(), nullable=False),
        sa.Column("attested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tagged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("already_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "length(btrim(programme)) >= 2", name="ck_enrolment_programme_not_blank"
        ),
        sa.CheckConstraint(
            "created_count >= 0 AND tagged_count >= 0 AND already_count >= 0 AND error_count >= 0",
            name="ck_enrolment_counts",
        ),
    )
    op.create_index("ix_enrolment_batches_created_at", "enrolment_batches", ["created_at"])

    op.create_table(
        "enrolment_batch_members",
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "candidate_profiles.id", ondelete="CASCADE", name="fk_enrolment_members_profile"
            ),
            primary_key=True,
        ),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "enrolment_batches.id", ondelete="CASCADE", name="fk_enrolment_members_batch"
            ),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.CheckConstraint(one_of("outcome", _OUTCOMES), name="ck_enrolment_member_outcome"),
    )
    op.create_index("ix_enrolment_batch_members_batch_id", "enrolment_batch_members", ["batch_id"])

    _widen(_EVENTS_BEFORE + ("enrolment_applied",))


def downgrade() -> None:
    op.execute("DELETE FROM analytics_events WHERE name = 'enrolment_applied'")
    _widen(_EVENTS_BEFORE)
    op.drop_index("ix_enrolment_batch_members_batch_id", table_name="enrolment_batch_members")
    op.drop_table("enrolment_batch_members")
    op.drop_index("ix_enrolment_batches_created_at", table_name="enrolment_batches")
    op.drop_table("enrolment_batches")
