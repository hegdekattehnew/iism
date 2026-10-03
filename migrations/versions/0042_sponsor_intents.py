"""An employer may offer to sponsor the one standard a near-miss candidate lacks

Revision ID: 0042
Revises: 0041
Create Date: 2026-10-03

Sprint 41, "hire and train" (ADR-048). An employer looking at the candidates
who are missing exactly one mandatory standard can offer to sponsor the course
that closes it. The candidate is told, in-app, and the offer links to the
vacancy, where applying is the consent act.

`sponsor_intents` is a table rather than an analytics event because it is a
durable fact with a lifecycle -- offered once, per vacancy and candidate, never
twice -- and the unique constraint is what makes "told once" a property of the
database rather than an intention, the `job_alerts` move one table over.

Two CHECK widenings, hand-written for the reason they always are here:
**Alembic does not diff CHECK constraint bodies**, so a name added to a tuple in
the model alone is accepted by the model and rejected by the database -- and
`record()` swallows its own failures, so the only symptom is events that
silently never appear. The value tuples are **frozen**, not imported: a
migration describes one moment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEMPLATES_BEFORE = (
    "application_received",
    "application_status_changed",
    "course_interest_registered",
    "organisation_invitation",
    "job_alert",
    "vacancy_closed",
    "course_interest_status_changed",
)
_TEMPLATES_ADDED = ("sponsor_offer",)

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
)
_EVENTS_ADDED = ("sponsor_intent_recorded",)


def upgrade() -> None:
    op.create_table(
        "sponsor_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        # The one standard offered. SET NULL, not CASCADE: a retired standard
        # must not take the record of an offer already made with it.
        sa.Column("skill_id", sa.Uuid(), nullable=True),
        # Who made the offer, for audit. SET NULL on their own erasure.
        sa.Column("offered_by_user_id", sa.Uuid(), nullable=True),
        # NULL when the candidate was not told: they opted out of unsolicited
        # messages, or had reached today's cap. The employer's offer is still a
        # fact, and the employer is never told which of the two happened.
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_sponsor_intents_job_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name="fk_sponsor_intents_profile_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skills.id"], name="fk_sponsor_intents_skill_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["offered_by_user_id"],
            ["users.id"],
            name="fk_sponsor_intents_offered_by_user_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("job_id", "profile_id", name="uq_sponsor_intent_job_profile"),
    )
    op.create_index("ix_sponsor_intents_job_id", "sponsor_intents", ["job_id"])
    op.create_index(
        "ix_sponsor_intents_profile_created", "sponsor_intents", ["profile_id", "created_at"]
    )

    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template",
        "notifications",
        one_of("template", _TEMPLATES_BEFORE + _TEMPLATES_ADDED),
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name",
        "analytics_events",
        one_of("name", _EVENTS_BEFORE + _EVENTS_ADDED),
    )


def downgrade() -> None:
    op.execute("DELETE FROM analytics_events WHERE name = 'sponsor_intent_recorded'")
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _EVENTS_BEFORE)
    )

    op.execute("DELETE FROM notifications WHERE template = 'sponsor_offer'")
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", _TEMPLATES_BEFORE)
    )

    op.drop_index("ix_sponsor_intents_profile_created", table_name="sponsor_intents")
    op.drop_index("ix_sponsor_intents_job_id", table_name="sponsor_intents")
    op.drop_table("sponsor_intents")
