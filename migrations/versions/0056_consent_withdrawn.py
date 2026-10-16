"""consent withdrawn, keeping the account

Revision ID: 0056
Revises: 0055
Create Date: 2026-10-17

Sprint 72 (ADR-082). One nullable column on `users`: when the person withdrew consent without
deleting their account. Not backfilled: nobody has withdrawn yet, and writing a value into old rows
would fabricate a withdrawal that did not happen.

`ix_users_consent_withdrawn` is a **partial** index (`WHERE consent_withdrawn_at IS NOT NULL`),
created with raw SQL so it is in `MANUALLY_MANAGED_INDEXES`. It holds only the people who withdrew,
which is what `marketplace.paused_profile()` reads on every employer shortlist and every people
figure: an uncorrelated subquery over a handful of rows, hashed once, instead of a probe per
candidate (the first, correlated version cost the shortlist ~100 ms at p95 at 50,000 candidates).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("consent_withdrawn_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "CREATE INDEX ix_users_consent_withdrawn ON users (id) WHERE consent_withdrawn_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_consent_withdrawn")
    op.drop_column("users", "consent_withdrawn_at")
