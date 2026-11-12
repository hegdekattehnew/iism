"""batch notices: a learner is told a batch starts soon or has filled

Revision ID: 0064
Revises: 0063
Create Date: 2026-11-12

Sprint 101 (ADR-103, BL-20.4). `batches.start_notice_at` records that the learners with a live
interest were told the batch is about to start; the worker stamps it **before** queuing, so a crash
costs the rest of one batch's reminders and never sends one twice. Two notification templates are
added to a closed set Alembic does not diff (`batch_starting`, `batch_full`), the list **frozen here**.

Nothing is backfilled: every existing batch has `start_notice_at` NULL, which would tell the learners
of an already-published batch that starts within three days on the first sweep. That is the point of
the column (they were never told), and the sweep only ever looks at batches that have not started.
The downgrade removes the notices the new names wrote first.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    "grievance_update",
    "listing_removed",
    "listing_restored",
    "application_status_message",
    "centre_verified",
    "centre_verification_revoked",
    "centre_manager_invitation",
    "delivery_requested",
    "delivery_invited",
    "delivery_approved",
    "delivery_declined",
    "delivery_revoked",
    "batch_cancelled",
    "batch_interest_registered",
    "batch_interest_status_changed",
)
_TEMPLATES_ADDED = ("batch_starting", "batch_full")


def _widen(values: tuple[str, ...]) -> None:
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", values)
    )


def upgrade() -> None:
    op.add_column(
        "batches", sa.Column("start_notice_at", sa.DateTime(timezone=True), nullable=True)
    )
    _widen(_TEMPLATES_BEFORE + _TEMPLATES_ADDED)


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template IN ('batch_starting', 'batch_full')")
    _widen(_TEMPLATES_BEFORE)
    op.drop_column("batches", "start_notice_at")
