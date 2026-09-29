"""Invitations: an organisation can have more than one person in it

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-22

Sprint 25. For twenty-four sprints every `Membership` was written with
`role="owner"` by one of three call sites, so `admin` and `member` were mapped
permission sets nothing could reach, and a sole owner deleting their account
destroyed the organisation and every application to it without a word.

Four parts. Three of them are hand-written, for two separate reasons that have
each cost time before:

* **Alembic does not diff CHECK constraint bodies.** A value added to a tuple in
  the model alone is accepted by the model and rejected by the database, and
  `record()` swallows its own failures -- so the only symptom of a forgotten
  widening is events that silently never appear.
* **A partial index is invisible to autogenerate's comparison** and is created
  here with `op.execute()`, so `uq_invitations_live` must also be listed in
  `MANUALLY_MANAGED_INDEXES` in `migrations/env.py` or the next autogenerate
  proposes dropping it.

The value tuples below are **frozen**, not imported from the models. A migration
describes one moment; importing the live tuple would make this revision produce a
wider constraint the day a later sprint adds a name.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `owner` is absent on purpose: ownership is transferred between people who are
# already members, never handed to a stranger holding a link.
_INVITABLE_ROLES = ("admin", "member")

# As of 0025.
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
)
_EVENTS_ADDED = (
    "member_invited",
    "member_invitation_accepted",
    "member_removed",
    "member_role_changed",
)

_TEMPLATES_BEFORE = (
    "application_received",
    "application_status_changed",
    "course_interest_registered",
)
_TEMPLATES_ADDED = ("organisation_invitation",)

_RECIPIENTS_BEFORE = ("user", "tenant")
_RECIPIENTS_ADDED = ("invitation",)


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # Named, every one: Alembic emits `create_foreign_key(None, ...)` whose
        # generated downgrade calls `drop_constraint(None, ...)` and fails.
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_invitations_tenant_id",
            ondelete="CASCADE",
        ),
        # SET NULL, not CASCADE: an inviter who later deletes their account
        # should stop being named, not take a live invitation with them.
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name="fk_invitations_invited_by_user_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(one_of("role", _INVITABLE_ROLES), name="ck_invitation_role"),
    )
    op.create_index("ix_invitations_token_hash", "invitations", ["token_hash"], unique=True)
    op.create_index("ix_invitations_tenant_id", "invitations", ["tenant_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    # One *live* invitation per address per organisation, in the database
    # rather than in a read-then-write that the second concurrent request
    # loses. Partial, so a revoked or accepted invitation does not block a new
    # one -- and therefore in `MANUALLY_MANAGED_INDEXES`.
    op.execute(
        "CREATE UNIQUE INDEX uq_invitations_live ON invitations (tenant_id, email) "
        "WHERE accepted_at IS NULL AND revoked_at IS NULL"
    )

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

    op.drop_constraint("ck_notification_recipient", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_recipient",
        "notifications",
        one_of("recipient_kind", _RECIPIENTS_BEFORE + _RECIPIENTS_ADDED),
    )


def downgrade() -> None:
    # Rows carrying a value the narrower constraint forbids would block it, and
    # a notification nobody can send is not worth keeping. Both notification
    # narrowings delete the same rows, so the template one runs first and the
    # recipient one finds nothing left to remove.
    op.execute("DELETE FROM notifications WHERE template IN ('organisation_invitation')")
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", _TEMPLATES_BEFORE)
    )

    op.execute("DELETE FROM notifications WHERE recipient_kind IN ('invitation')")
    op.drop_constraint("ck_notification_recipient", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_recipient",
        "notifications",
        one_of("recipient_kind", _RECIPIENTS_BEFORE),
    )

    op.execute(
        "DELETE FROM analytics_events WHERE name IN "
        "('member_invited', 'member_invitation_accepted', 'member_removed', "
        "'member_role_changed')"
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _EVENTS_BEFORE)
    )

    op.execute("DROP INDEX IF EXISTS uq_invitations_live")
    op.drop_index("ix_invitations_email", table_name="invitations")
    op.drop_index("ix_invitations_tenant_id", table_name="invitations")
    op.drop_index("ix_invitations_token_hash", table_name="invitations")
    op.drop_table("invitations")
