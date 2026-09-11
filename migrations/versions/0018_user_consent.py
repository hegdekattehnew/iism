"""Record which privacy notice each account agreed to, and when

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-11

India's Digital Personal Data Protection Act 2023 makes consent the basis for
processing personal data, and consent must be provable. Until now signup asked
for nothing and stored nothing: there was no way to show that anyone had agreed
to anything, or to which text.

Nullable, not backfilled. Accounts created before this migration did not give
consent through a recorded notice, and writing a version into their rows would
fabricate a record of something that never happened. They stay null until the
person agrees through a form that records it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("consent_version", sa.String(), nullable=True))
    op.add_column("users", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "consented_at")
    op.drop_column("users", "consent_version")
