"""An index for the hourly sweep that closes vacancies whose date has passed

Revision ID: 0049
Revises: 0048
Create Date: 2026-10-07

Sprint 52. `close_expired_jobs` runs every hour and asks for vacancies that are still open and
have a closing date in the past. Nothing indexed `closes_at`, so the question was a scan of every
vacancy there is, every hour. The index is **partial** (`closes_at IS NOT NULL AND closed_at IS
NULL`): it holds only the vacancies the sweep can still act on, so it stays small however large
the catalogue and however many have closed.

Declared on the model too, so Alembic sees it and `alembic check` stays clean. No data change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_closing",
        "jobs",
        ["closes_at"],
        postgresql_where=sa.text("closes_at IS NOT NULL AND closed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jobs_closing",
        table_name="jobs",
        postgresql_where=sa.text("closes_at IS NOT NULL AND closed_at IS NULL"),
    )
