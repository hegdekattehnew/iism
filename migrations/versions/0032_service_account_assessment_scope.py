"""Widen service account scope for assessment-provider writes

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-26

Sprint 35, BL-3.1. `SERVICE_ACCOUNT_SCOPES` was a set of one -- `read` -- since
Sprint 33; an assessment provider's webhook needs to write a `CandidateSkill`,
which no existing key may do. `assessment:write` is additive: every issued key
today is `read` and keeps behaving exactly as before.

The CHECK is rewritten by hand, as in 0020/0024/0027/0031: Alembic does not
diff CHECK constraint bodies.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = ("read",)
_ADDED = ("assessment:write",)


def upgrade() -> None:
    op.drop_constraint("ck_service_account_scope", "service_accounts", type_="check")
    op.create_check_constraint(
        "ck_service_account_scope", "service_accounts", one_of("scope", _BEFORE + _ADDED)
    )


def downgrade() -> None:
    # A key carrying the scope the narrower constraint forbids would block it
    # -- revoke rather than delete, matching ServiceAccount's own "never
    # deleted" rule; a revoked row still satisfies any CHECK on scope.
    op.execute(
        "UPDATE service_accounts SET revoked_at = now() "
        "WHERE scope = 'assessment:write' AND revoked_at IS NULL"
    )
    op.execute("UPDATE service_accounts SET scope = 'read' WHERE scope = 'assessment:write'")
    op.drop_constraint("ck_service_account_scope", "service_accounts", type_="check")
    op.create_check_constraint(
        "ck_service_account_scope", "service_accounts", one_of("scope", _BEFORE)
    )
