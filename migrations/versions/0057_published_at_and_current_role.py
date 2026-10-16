"""a vacancy's posted date, and the role a candidate says they do now

Revision ID: 0057
Revises: 0056
Create Date: 2026-10-18

Sprint 74 (ADR-084). Two nullable columns, neither backfilled.

`jobs.published_at` is when a vacancy last went live. Every vacancy published before this column
existed keeps NULL: `created_at` is the draft's date and `updated_at` moves on every edit, so an
existing row's real date is unknown and the clients render nothing for NULL rather than an invented
"posted n days ago". No index: the default listing order is by title, and nothing filters on it.

`candidate_profiles.current_role_slug` is the qualification a candidate confirmed as the work they do
now (BL-6.5). A slug and not a foreign key, on purpose: the NSQF importer rewrites the taxonomy, and a
role that disappears should fall back to the guess rather than break a profile.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidate_profiles", sa.Column("current_role_slug", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate_profiles", "current_role_slug")
    op.drop_column("jobs", "published_at")
