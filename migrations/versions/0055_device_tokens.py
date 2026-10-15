"""device tokens, and a stamp for the push sweep

Revision ID: 0055
Revises: 0054
Create Date: 2026-10-15

Sprint 65 (BL-15.6, ADR-075). One table, one column and one partial index.

`device_tokens` holds the phones a person has signed in on, so the worker can send a push. A token
is unique (it belongs to one person at a time) and erased with the account (`ON DELETE CASCADE`).

`notifications.pushed_at` is when the worker dealt with an in-app notice for push: sent it to the
person's phones, found there was nothing to send, or gave up. `NULL` means still owed a look.

**Every existing row is stamped at once.** Without that, the first sweep after this migration would
find the whole in-app backlog "not yet pushed" and send a lock-screen alert for every notice in it,
to anybody who happens to register a phone: the difference between switching a feature on and an
incident (Sprint 27's `alerted_at` backfill, for the same reason).

`ix_notifications_unpushed` is the sweep's own query and is partial (in-app, to a person, not yet
dealt with), created after the backfill so it is built over an empty set rather than the backlog.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLATFORMS = ("android", "ios")


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False, server_default="en"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(one_of("platform", _PLATFORMS), name="ck_device_token_platform"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_device_tokens_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_device_tokens_token"),
    )
    op.create_index("ix_device_tokens_user", "device_tokens", ["user_id"])

    op.add_column("notifications", sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE notifications SET pushed_at = now()")
    op.create_index(
        "ix_notifications_unpushed",
        "notifications",
        ["created_at"],
        postgresql_where=sa.text(
            "channel = 'in_app' AND recipient_kind = 'user' AND pushed_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_unpushed", table_name="notifications")
    op.drop_column("notifications", "pushed_at")
    op.drop_index("ix_device_tokens_user", table_name="device_tokens")
    op.drop_table("device_tokens")
