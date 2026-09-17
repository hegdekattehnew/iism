"""The notification outbox

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-17

Sprint 21 closed the loop and told nobody. This is the queue that fixes it.

A table rather than a direct send, because delivery must never fail a request
(ADR-006): an SMTP timeout while someone is applying would otherwise lose the
application. The row names a recipient and does not hold their address -- that
is resolved at send time, so contact details stay out of a table that gets
dumped and out of any log line that renders a row (ADR-023).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recipient_kind", sa.String(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("template", sa.String(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("locale", sa.String(), nullable=False, server_default="en"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        # Byte-identical to what `one_of` puts in the model: Alembic does not
        # diff CHECK bodies, and `tests/test_enumerations.py` compares them.
        sa.CheckConstraint("recipient_kind IN ('user', 'tenant')", name="ck_notification_recipient"),
        sa.CheckConstraint("channel IN ('email', 'in_app')", name="ck_notification_channel"),
        sa.CheckConstraint("template IN ('application_received', 'application_status_changed')", name="ck_notification_template"),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed', 'skipped')", name="ck_notification_status"),
    )
    op.create_index("ix_notifications_pending", "notifications", ["status", "created_at"])
    op.create_index(
        "ix_notifications_recipient",
        "notifications",
        ["recipient_kind", "recipient_id", "read_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_recipient", table_name="notifications")
    op.drop_index("ix_notifications_pending", table_name="notifications")
    op.drop_table("notifications")
