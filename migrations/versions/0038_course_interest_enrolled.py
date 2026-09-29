"""Course interest gains a provider-reported "enrolled" status

Revision ID: 0038
Revises: 0037
Create Date: 2026-09-29

Sprint 38, ADR-047. ADR-025 named "provider-reported enrolment conversion" as
one of three metrics that must be citable before any billing code is written
(BL-1.3); ADR-043 (Sprint 34) built the payment adapter port but explicitly
declined to close that gap, because no surface existed for a provider to
report an enrolment on at all. This widens `course_interests`' own status set
rather than adding a table -- the row already distinguishes the learner's
moves (`registered`, `withdrawn`) from the provider's (`contacted`), and
`enrolled` is one more of the provider's, at the same self-reported trust
level `contacted` already carries.

Hand-written, frozen `_BEFORE`/`_ADDED` tuples, never imported from the live
model constant, per this codebase's standing rule that Alembic does not diff
CHECK bodies.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INTEREST_STATUS_BEFORE = ("registered", "withdrawn", "contacted")
_INTEREST_STATUS_ADDED = ("enrolled",)


def upgrade() -> None:
    op.drop_constraint("ck_course_interest_status", "course_interests", type_="check")
    op.create_check_constraint(
        "ck_course_interest_status",
        "course_interests",
        one_of("status", _INTEREST_STATUS_BEFORE + _INTEREST_STATUS_ADDED),
    )


def downgrade() -> None:
    # Truthful rollback: an enrolled learner was, at minimum, contacted --
    # falling back to `registered` would erase that they were ever reached.
    op.execute("UPDATE course_interests SET status = 'contacted' WHERE status = 'enrolled'")
    op.drop_constraint("ck_course_interest_status", "course_interests", type_="check")
    op.create_check_constraint(
        "ck_course_interest_status", "course_interests", one_of("status", _INTEREST_STATUS_BEFORE)
    )
