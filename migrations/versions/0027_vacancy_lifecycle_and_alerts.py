"""Vacancy lifecycle, and the alerts that reach people between visits

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-23

Sprint 27. "Hired" did nothing to the vacancy for twenty-six sprints: it stayed
published, kept ranking in strangers' matches and kept taking applications. And
`match_jobs` ran only inside a request handler, so a vacancy published on Monday
reached a matched candidate only if they happened to open `/matches`.

Five parts, and the CHECK widenings are hand-written for the reason they always
are here: **Alembic does not diff CHECK constraint bodies**, so a name added to
a tuple in the model alone is accepted by the model and rejected by the
database -- and `record()` swallows its own failures, so the only symptom is
events that silently never appear.

The value tuples are **frozen**, not imported. A migration describes one
moment; importing the live tuple would make this revision produce a wider
constraint the day a later sprint adds a name.

`positions` and `job_alerts_enabled` ship with server defaults because the
tables are not empty: every existing vacancy is a vacancy for one person until
somebody says otherwise, and every existing candidate wants to hear about work
-- that is why they have a profile.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLOSE_REASONS = ("filled", "withdrawn", "expired")

# As of 0026.
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
)
_EVENTS_ADDED = ("job_closed", "job_reopened", "job_alerts_sent")

_TEMPLATES_BEFORE = (
    "application_received",
    "application_status_changed",
    "course_interest_registered",
    "organisation_invitation",
)
_TEMPLATES_ADDED = ("job_alert", "vacancy_closed")


def upgrade() -> None:
    # --- 1. the vacancy's lifecycle ---------------------------------------
    op.add_column("jobs", sa.Column("positions", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("jobs", sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("close_reason", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True))

    op.create_check_constraint(
        "ck_jobs_close_reason", "jobs", one_of("close_reason", _CLOSE_REASONS, nullable=True)
    )
    # The two closure columns move together or not at all.
    op.create_check_constraint(
        "ck_jobs_closed", "jobs", "(closed_at IS NULL) = (close_reason IS NULL)"
    )
    op.create_check_constraint("ck_jobs_positions", "jobs", "positions >= 1")
    op.create_index("ix_jobs_alerted_at", "jobs", ["alerted_at"])
    op.create_index("ix_jobs_status_closed", "jobs", ["status", "closed_at"])

    # **Every existing vacancy is alerted-as-of-now, not null.** Otherwise the
    # first sweep after this migration treats the entire back catalogue as new
    # and mails every candidate about every job ever published. Backfilling the
    # stamp is the difference between switching a feature on and an incident.
    op.execute("UPDATE jobs SET alerted_at = now()")

    # --- 2. the candidate's opt-out ---------------------------------------
    op.add_column(
        "candidate_profiles",
        sa.Column("job_alerts_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )

    # --- 3. who has been told what ----------------------------------------
    op.create_table(
        "job_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # Named, every one: Alembic emits `create_foreign_key(None, ...)` whose
        # generated downgrade calls `drop_constraint(None, ...)` and fails.
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_job_alerts_job_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name="fk_job_alerts_profile_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("job_id", "profile_id", name="uq_job_alert_job_profile"),
    )
    op.create_index("ix_job_alerts_job_id", "job_alerts", ["job_id"])
    op.create_index(
        "ix_job_alerts_profile_created", "job_alerts", ["profile_id", "created_at"]
    )

    # --- 4 & 5. the two hand-widened CHECKs -------------------------------
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
    op.execute("DELETE FROM notifications WHERE template IN ('job_alert', 'vacancy_closed')")
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", _TEMPLATES_BEFORE)
    )

    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('job_closed', 'job_reopened', 'job_alerts_sent')"
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _EVENTS_BEFORE)
    )

    op.drop_index("ix_job_alerts_profile_created", table_name="job_alerts")
    op.drop_index("ix_job_alerts_job_id", table_name="job_alerts")
    op.drop_table("job_alerts")

    op.drop_column("candidate_profiles", "job_alerts_enabled")

    op.drop_index("ix_jobs_status_closed", table_name="jobs")
    op.drop_index("ix_jobs_alerted_at", table_name="jobs")
    op.drop_constraint("ck_jobs_positions", "jobs", type_="check")
    op.drop_constraint("ck_jobs_closed", "jobs", type_="check")
    op.drop_constraint("ck_jobs_close_reason", "jobs", type_="check")
    op.drop_column("jobs", "alerted_at")
    op.drop_column("jobs", "close_reason")
    op.drop_column("jobs", "closed_at")
    op.drop_column("jobs", "closes_at")
    op.drop_column("jobs", "positions")
