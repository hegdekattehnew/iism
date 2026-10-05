"""Two indexes the scale harness showed were missing

Revision ID: 0047
Revises: 0046
Create Date: 2026-10-05

Sprint 50 (ADR-060). Both found by measuring, on 500,000 pending in-app notifications and
5,000 applications to one vacancy, not by reading.

* `ix_notifications_pending_email` -- partial, `(created_at) WHERE status = 'pending' AND
  channel = 'email'`. The drain runs every minute and wants the oldest pending *email* rows;
  the existing `(status, created_at)` index cannot say `channel`, and in-app notices are never
  moved off `pending` (only the email loop sets a status), so each tick walked the whole in-app
  backlog first. The existing index stays: other readers use it.
* `ix_applications_job_status` -- `(job_id, status)`, which the employer overview's per-vacancy
  `GROUP BY job_id, status` reads without touching the table.

No data change, and both are created and dropped by name, so the round trip is exact.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_notifications_pending_email",
        "notifications",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending' AND channel = 'email'"),
    )
    op.create_index("ix_applications_job_status", "applications", ["job_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_applications_job_status", table_name="applications")
    op.drop_index("ix_notifications_pending_email", table_name="notifications")
