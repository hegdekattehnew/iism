"""An organisation gets a profile

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-07

`tenants` has carried only slug, name, type and city since Sprint 3, so a job
listing showed a bare employer name with nothing behind it — and `city` was
never written by application code at all, only by the seed script. A candidate
deciding whether to apply had nothing to decide on.

`contact_email` is deliberately absent from the public `TenantOut`: an
organisation's inbox is not something a job listing should broadcast.

`is_verified` is set by an operator, never by the organisation. A self-asserted
badge is worse than none, because a candidate reads it as ours. Nothing writes
it yet; the column exists so the seam is there before anyone needs it.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Free prose is Text, never String(n). Two import runs have already died on
    # a varchar bound that looked generous at the time.
    op.add_column("tenants", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("website", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("logo_url", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("contact_email", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "tenants",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    for column in (
        "updated_at",
        "is_verified",
        "contact_email",
        "logo_url",
        "website",
        "description",
    ):
        op.drop_column("tenants", column)
