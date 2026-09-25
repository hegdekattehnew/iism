"""Service accounts

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-25

Sprint 33, BL-7.2. The external-system actor's thin slice: a credential for a
partner integration, alongside JWT rather than layered under it. The key is
hashed the same way an OTP is (HMAC on `JWT_SECRET_KEY`) -- a leaked database
dump must not itself be a working credential. Revoked rather than deleted:
`revoked_at` is what a log line's `service_account_id` still resolves against.

`scope` is a closed set of one value today (`SERVICE_ACCOUNT_SCOPES` in
`api/modules/identity/models.py`); the CHECK is hand-written for the reason it
always is here -- Alembic does not diff CHECK constraint bodies.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("hashed_key", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("scope IN ('read')", name="ck_service_account_scope"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_service_accounts_hashed_key", "service_accounts", ["hashed_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_service_accounts_hashed_key", table_name="service_accounts")
    op.drop_table("service_accounts")
