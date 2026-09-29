"""Gig work reuses Job; application outcomes and reviews

Revision ID: 0037
Revises: 0036
Create Date: 2026-09-29

Sprint 37, Epic B8, ADR-046 (supersedes ADR-045 §1-4). A gig is a temporary
job assignment, treated as a `Job` rather than a separate model -- verified
against the code before this was written: `open_job()`, `match_jobs`'s
retrieval SQL, `score_match` and the existing hourly `close_expired_jobs`
worker cron contain zero references to `employment_type`, so a `Job` row
with `employment_type='gig'`, a real `closes_at` and a real `positions`
count flows through the existing matching, ranking and auto-close pipeline
with no code change to any of those three files.

Four CHECK widenings and one new table, bundled the way 0027 bundled several
related changes from one sprint. Every widened CHECK is hand-written --
Alembic does not diff CHECK bodies -- with frozen `_BEFORE`/`_ADDED` tuples,
never imported from the live model constants: this migration describes one
moment, and importing the live tuple would make it produce a wider
constraint the day a later sprint adds a value.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMPLOYMENT_BEFORE = ("full_time", "part_time", "contract", "apprenticeship")
_EMPLOYMENT_ADDED = ("gig",)

_APPLICATION_STATUS_BEFORE = ("applied", "withdrawn", "shortlisted", "rejected", "hired")
_APPLICATION_STATUS_ADDED = ("completed", "no_show")

_EVENT_NAMES_BEFORE = (
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
)
_EVENT_NAMES_ADDED = ("application_review_submitted",)

_REVIEW_SUBJECT_ROLES = ("poster", "worker")


def upgrade() -> None:
    op.drop_constraint("ck_jobs_employment_type", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_employment_type",
        "jobs",
        one_of("employment_type", _EMPLOYMENT_BEFORE + _EMPLOYMENT_ADDED),
    )

    op.drop_constraint("ck_candidate_preferred_employment", "candidate_profiles", type_="check")
    op.create_check_constraint(
        "ck_candidate_preferred_employment",
        "candidate_profiles",
        one_of("preferred_employment_type", _EMPLOYMENT_BEFORE + _EMPLOYMENT_ADDED, nullable=True),
    )

    op.drop_constraint("ck_application_status", "applications", type_="check")
    op.create_check_constraint(
        "ck_application_status",
        "applications",
        one_of("status", _APPLICATION_STATUS_BEFORE + _APPLICATION_STATUS_ADDED),
    )

    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name",
        "analytics_events",
        one_of("name", _EVENT_NAMES_BEFORE + _EVENT_NAMES_ADDED),
    )

    op.create_table(
        "application_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("subject_role", sa.String(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            one_of("subject_role", _REVIEW_SUBJECT_ROLES), name="ck_review_subject_role"
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_application_reviews_application",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name="fk_application_reviews_author",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "application_id", "subject_role", name="uq_application_review_direction"
        ),
    )


def downgrade() -> None:
    op.drop_table("application_reviews")

    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _EVENT_NAMES_BEFORE)
    )

    # Truthful rollback values, not guesses: a completed/no-show application
    # was hired before either outcome was recorded.
    op.execute("UPDATE applications SET status = 'hired' WHERE status IN ('completed', 'no_show')")
    op.drop_constraint("ck_application_status", "applications", type_="check")
    op.create_check_constraint(
        "ck_application_status", "applications", one_of("status", _APPLICATION_STATUS_BEFORE)
    )

    # NULL, not a guessed preference -- "no preference stated" is the only
    # truthful value once "gig" cannot be represented.
    op.execute(
        "UPDATE candidate_profiles SET preferred_employment_type = NULL "
        "WHERE preferred_employment_type = 'gig'"
    )
    op.drop_constraint("ck_candidate_preferred_employment", "candidate_profiles", type_="check")
    op.create_check_constraint(
        "ck_candidate_preferred_employment",
        "candidate_profiles",
        one_of("preferred_employment_type", _EMPLOYMENT_BEFORE, nullable=True),
    )

    # Lossy, not truthful -- there is no remaining value that means "gig."
    # Falls back to `Job.employment_type`'s own column default, the same
    # target every other field on this row falls back to when nothing better
    # is known.
    op.execute("UPDATE jobs SET employment_type = 'full_time' WHERE employment_type = 'gig'")
    op.drop_constraint("ck_jobs_employment_type", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_employment_type", "jobs", one_of("employment_type", _EMPLOYMENT_BEFORE)
    )
