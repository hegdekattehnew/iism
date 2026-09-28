"""Operator authority tiers

Revision ID: 0036
Revises: 0035
Create Date: 2026-09-28

Sprint 37, BL-7.3, ADR-044. `users.is_staff` has been a single boolean since
0028: every operator gets every `OPS_*` permission, including
`OPS_ORG_VERIFY` -- the one decision with public blast radius, since every
visitor sees the "Verified" badge it grants. This gives operator authority a
second dimension without touching the flag ADR-042 already locked down: still
no HTTP writer, still only `scripts/grant_staff.py`.

`staff_tier` is `NULL` iff `is_staff` is false -- `ck_users_staff_tier_pairs_
with_flag` makes "staff with no tier" and "tiered but not staff" both
unrepresentable, the same shape 0028 used for `tenants.verified_at`/
`verified_by`.

**Backfill: every existing `is_staff = true` row becomes `admin`.** Not a
default chosen for convenience -- a boolean's only honest equivalent tier is
the one with no restrictions. Anything narrower would silently take access
away from an account that already had it, the moment this migration ran.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen, per the reason every hand-written CHECK migration in this codebase
# gives: a migration describes one moment, and importing the live tuple would
# make this revision produce a wider constraint the day a later sprint adds a
# tier.
STAFF_TIERS = ("support", "admin")


def upgrade() -> None:
    op.add_column("users", sa.Column("staff_tier", sa.String(), nullable=True))

    # Every existing operator, before the CHECK below could refuse the
    # otherwise-inconsistent NULL. See the module docstring for why `admin`.
    op.execute("UPDATE users SET staff_tier = 'admin' WHERE is_staff")

    op.create_check_constraint(
        "ck_users_staff_tier",
        "users",
        "staff_tier IS NULL OR staff_tier IN (" + ", ".join(f"'{t}'" for t in STAFF_TIERS) + ")",
    )
    op.create_check_constraint(
        "ck_users_staff_tier_pairs_with_flag",
        "users",
        "(is_staff AND staff_tier IS NOT NULL) OR (NOT is_staff AND staff_tier IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_staff_tier_pairs_with_flag", "users", type_="check")
    op.drop_constraint("ck_users_staff_tier", "users", type_="check")
    op.drop_column("users", "staff_tier")
