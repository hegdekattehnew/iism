"""centre managers: a role that exists only on a training centre

Revision ID: 0060
Revises: 0059
Create Date: 2026-10-23

Sprint 96 (ADR-102, BL-18.4). The person who runs a centre day to day holds the new role
`manager` on the **centre's own tenant row**: a membership, so signing in, leaving and erasure work
as they do for everybody, and an invitation, so the existing flow brings them in. Three closed sets
Alembic does not diff are widened by hand, each list frozen here: the membership roles and the
invitation roles gain `manager`, and the notification templates gain `centre_manager_invitation`.

That `manager` appears only on a training centre (and nothing else does) is a rule about two tables
and is enforced in `identity/centre_staff.py`, the only writer, not by a CHECK.

The downgrade removes every manager membership, invitation and queued invitation notice first: a
row of a role the older constraint refuses cannot stay.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEMBERSHIP_BEFORE = ("owner", "admin", "member")
_INVITATION_BEFORE = ("admin", "member")
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
)


def _widen(table: str, constraint: str, column: str, values: tuple[str, ...]) -> None:
    op.drop_constraint(constraint, table, type_="check")
    op.create_check_constraint(constraint, table, one_of(column, values))


def upgrade() -> None:
    _widen("memberships", "ck_membership_role", "role", (*_MEMBERSHIP_BEFORE, "manager"))
    _widen("invitations", "ck_invitation_role", "role", (*_INVITATION_BEFORE, "manager"))
    _widen(
        "notifications",
        "ck_notification_template",
        "template",
        (*_TEMPLATES_BEFORE, "centre_manager_invitation"),
    )


def downgrade() -> None:
    op.execute("DELETE FROM notifications WHERE template = 'centre_manager_invitation'")
    op.execute("DELETE FROM invitations WHERE role = 'manager'")
    op.execute("DELETE FROM memberships WHERE role = 'manager'")
    _widen("notifications", "ck_notification_template", "template", _TEMPLATES_BEFORE)
    _widen("invitations", "ck_invitation_role", "role", _INVITATION_BEFORE)
    _widen("memberships", "ck_membership_role", "role", _MEMBERSHIP_BEFORE)
