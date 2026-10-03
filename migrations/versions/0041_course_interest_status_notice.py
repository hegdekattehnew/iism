"""A learner is told when a provider marks their interest contacted or enrolled

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-03

Sprint 41. `provider_service.set_status` was deliberately silent to the learner,
on the reasoning that the provider phones them anyway. The owner decided
otherwise: a free in-app notice for both statuses, so the learner sees the
outcome even when the call was missed.

A new template name is a hand-written CHECK widening, for the reason it always
is here: **Alembic does not diff CHECK constraint bodies**, so a name added to
`TEMPLATES` in the model alone is accepted by the model and rejected by the
database, and the notice would simply never be written.

The value tuple is **frozen**, not imported. A migration describes one moment;
importing the live tuple would make this revision produce a wider constraint
the day a later sprint adds a name.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEMPLATES_BEFORE = (
    "application_received",
    "application_status_changed",
    "course_interest_registered",
    "organisation_invitation",
    "job_alert",
    "vacancy_closed",
)
_TEMPLATES_ADDED = ("course_interest_status_changed",)


def upgrade() -> None:
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template",
        "notifications",
        one_of("template", _TEMPLATES_BEFORE + _TEMPLATES_ADDED),
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template = 'course_interest_status_changed'")
    op.drop_constraint("ck_notification_template", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notification_template", "notifications", one_of("template", _TEMPLATES_BEFORE)
    )
