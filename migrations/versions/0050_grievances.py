"""Grievances and contact messages (Sprint 57, BL-14.3, ADR-067).

A table of what people wrote to us and what became of it, and one in-app notice template for telling
a signed-in sender where their message stands.

The template list is **frozen** here rather than imported: a migration describes one moment, and
importing the live tuple would make 0050 produce a wider constraint the day a later sprint adds a
name.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from api.core.database import one_of

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS = ("contact", "grievance", "data_request")
_STATUSES = ("open", "acknowledged", "resolved", "dismissed")
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
)


def upgrade() -> None:
    op.create_table(
        "grievances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_grievances_user_id"),
            nullable=True,
        ),
        sa.Column("reply_to", sa.String(), nullable=True),
        sa.Column("locale", sa.String(), nullable=False, server_default="en"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column(
            "handled_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_grievances_handled_by"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("reference", name="uq_grievances_reference"),
        sa.CheckConstraint(one_of("kind", _KINDS), name="ck_grievances_kind"),
        sa.CheckConstraint(one_of("status", _STATUSES), name="ck_grievances_status"),
        sa.CheckConstraint("length(btrim(body)) BETWEEN 10 AND 4000", name="ck_grievances_body"),
        sa.CheckConstraint(
            "user_id IS NOT NULL OR reply_to IS NOT NULL", name="ck_grievances_reachable"
        ),
        sa.CheckConstraint(
            "kind <> 'data_request' OR user_id IS NOT NULL", name="ck_grievances_data_request_user"
        ),
        sa.CheckConstraint(
            "(status IN ('resolved', 'dismissed')) = (resolved_at IS NOT NULL)",
            name="ck_grievances_closed",
        ),
    )
    op.create_index("ix_grievances_status_created", "grievances", ["status", "created_at"])
    op.create_index("ix_grievances_user_id", "grievances", ["user_id"])

    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template",
        "notifications",
        one_of("template", _TEMPLATES_BEFORE + ("grievance_update",)),
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template = 'grievance_update'")
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", _TEMPLATES_BEFORE)
    )
    op.drop_index("ix_grievances_user_id", table_name="grievances")
    op.drop_index("ix_grievances_status_created", table_name="grievances")
    op.drop_table("grievances")
