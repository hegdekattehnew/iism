"""Tell an organisation when its Verified badge changes

Revision ID: 0044
Revises: 0043
Create Date: 2026-10-04

Sprint 43, BL-9.2. An operator's decision to grant or revoke an organisation's
Verified badge used to change what every candidate sees about that organisation
and tell the organisation nothing. It now queues one email, only when the badge
actually changes.

Two notification templates, hand-written into the CHECK for the reason these
always are here: **Alembic does not diff CHECK constraint bodies**, so a name
added to `TEMPLATES` alone is accepted by the model and rejected by the database
-- and here the failing write is the verification itself, because the notice is
queued in the same transaction as the decision. The value tuple is **frozen**
rather than imported: a migration describes one moment.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0044"
down_revision: str | None = "0043"
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
)
_TEMPLATES_ADDED = ("organisation_verified", "organisation_verification_revoked")


def upgrade() -> None:
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template",
        "notifications",
        one_of("template", _TEMPLATES_BEFORE + _TEMPLATES_ADDED),
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications WHERE template IN "
        "('organisation_verified', 'organisation_verification_revoked')"
    )
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", _TEMPLATES_BEFORE)
    )
