"""Course interests: the row that closes the third actor's loop

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-21

Sprint 24. A learner can now act on a recommended course, and the provider who
published it is told. Three parts, and two of them are hand-written because
**Alembic does not diff CHECK constraint bodies**: a name added to a tuple in
the model alone is accepted by the model and rejected by the database, and
`record()` swallows its own failures, so the only symptom is events that
silently never appear.

The value tuples below are **frozen**, not imported from the models. A
migration describes one moment; importing the live tuple would make this
revision produce a wider constraint the day a later sprint adds a name.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INTEREST_STATUSES = ("registered", "withdrawn", "contacted")

# As of 0024.
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
)
_EVENTS_ADDED = (
    "course_interest_registered",
    "course_interest_withdrawn",
    "course_interest_status_changed",
)

_TEMPLATES_BEFORE = ("application_received", "application_status_changed")
_TEMPLATES_ADDED = ("course_interest_registered",)


def upgrade() -> None:
    op.create_table(
        "course_interests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="registered"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("contact_shared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # Named, every one: Alembic emits `create_foreign_key(None, ...)` whose
        # generated downgrade calls `drop_constraint(None, ...)` and fails.
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name="fk_course_interests_course_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name="fk_course_interests_profile_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "course_id", "profile_id", name="uq_course_interest_course_profile"
        ),
        sa.CheckConstraint(
            one_of("status", _INTEREST_STATUSES), name="ck_course_interest_status"
        ),
    )
    op.create_index("ix_course_interests_course_id", "course_interests", ["course_id"])
    op.create_index("ix_course_interests_profile_id", "course_interests", ["profile_id"])

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
    # Rows carrying a value the narrower constraint forbids would block it, and
    # an event nobody can record is not worth keeping.
    op.execute(
        "DELETE FROM notifications WHERE template IN ('course_interest_registered')"
    )
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", _TEMPLATES_BEFORE)
    )

    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('course_interest_registered', 'course_interest_withdrawn', "
        "'course_interest_status_changed')"
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _EVENTS_BEFORE)
    )

    op.drop_index("ix_course_interests_profile_id", table_name="course_interests")
    op.drop_index("ix_course_interests_course_id", table_name="course_interests")
    op.drop_table("course_interests")
