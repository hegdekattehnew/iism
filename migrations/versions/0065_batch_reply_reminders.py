"""batch reply reminders: an organisation is told learners are still waiting for a reply

Revision ID: 0065
Revises: 0064
Create Date: 2026-11-12

Sprint 103 (ADR-103, BL-18.7). `batch_interests.reply_reminder_at` records that the organisation that
runs the batch was reminded of this learner. The worker stamps it **before** queuing (the alert
sweep's rule: a crash costs a reminder and never sends one twice), so each waiting learner is
mentioned once, ever, and one email per organisation carries a count and a link, nothing about who.
One notification template is added to a closed set Alembic does not diff (`batch_replies_owed`), the
list **frozen here**.

Nothing is backfilled: an organisation with learners already waiting more than three days gets one
email, once, on the first sweep, which is the point (nobody told them), and it is one email per
organisation however many are waiting. The downgrade removes the notices the new name wrote first.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0065"
down_revision: str | None = "0064"
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
    "batch_starting",
    "batch_full",
)
_TEMPLATES_ADDED = ("batch_replies_owed",)


def _widen(values: tuple[str, ...]) -> None:
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", values)
    )


def upgrade() -> None:
    op.add_column(
        "batch_interests",
        sa.Column("reply_reminder_at", sa.DateTime(timezone=True), nullable=True),
    )
    _widen(_TEMPLATES_BEFORE + _TEMPLATES_ADDED)


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template = 'batch_replies_owed'")
    _widen(_TEMPLATES_BEFORE)
    op.drop_column("batch_interests", "reply_reminder_at")
