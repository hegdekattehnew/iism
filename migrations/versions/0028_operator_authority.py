"""Operator authority, and a verified badge that carries its evidence

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-23

Sprint 28, and ADR-042. `tenants.is_verified` has existed since 0016 with **no
writer at all** -- a column definition, a read on the public payload, a read in
the interface, and a test asserting it cannot be written. A marketplace whose
verified badge nobody can grant has no verified organisations.

This gives it one, and in the same motion replaces it. The badge is now
*derived* from `verified_at`, so "verified with no provenance" stops being
representable rather than merely being constrained. **Nothing is lost by the
drop**: no code path ever wrote the boolean, so no row can disagree with the
timestamp -- which is also why this refactor is free in this revision and would
be a data audit in any later one.

The CHECKs are hand-written for the reason they always are here: **Alembic does
not diff CHECK constraint bodies**. The value tuple is **frozen**, not imported
from `operations.models` -- a migration describes one moment, and importing the
live tuple would make this revision produce a wider constraint the day a later
sprint adds a decision.

`users.is_staff` ships `server_default=false` because the table is not empty and
because the safe value is the only acceptable one: an existing account must not
acquire operator authority by migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen. See the module docstring.
VERIFICATION_DECISIONS = ("granted", "revoked")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.add_column(
        "tenants",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("tenants", sa.Column("verified_by", sa.Uuid(), nullable=True))
    op.add_column("tenants", sa.Column("verification_note", sa.Text(), nullable=True))
    # Named explicitly. An unnamed FK makes Alembic emit
    # `drop_constraint(None, ...)` in the downgrade, which fails -- twelve of
    # those appeared across 0011 and 0012.
    op.create_foreign_key(
        "fk_tenants_verified_by_users",
        "tenants",
        "users",
        ["verified_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_tenants_verified_has_evidence",
        "tenants",
        "verified_at IS NULL OR ("
        "verified_by IS NOT NULL AND length(btrim(verification_note)) >= 10)",
    )

    # No backfill, and that is the decision. Every row's `is_verified` is false
    # -- nothing has ever set it -- so leaving `verified_at` NULL preserves the
    # data exactly. Writing a timestamp into any row would fabricate a
    # verification nobody performed, the same reasoning 0018 applied to consent.
    op.drop_column("tenants", "is_verified")

    op.create_table(
        "tenant_verification_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        # SET NULL: an operator may exercise their own erasure, and the record
        # about the organisation has to survive them.
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            # clock_timestamp(), not now(): `now()` is the transaction start
            # time, so two decisions taken in one transaction share an instant
            # and the history has no order. See the model's comment.
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _one_of("decision", VERIFICATION_DECISIONS), name="ck_verification_decision"
        ),
        sa.CheckConstraint("length(btrim(note)) >= 10", name="ck_verification_note_not_blank"),
    )
    op.create_index(
        "ix_tenant_verification_events_tenant_id", "tenant_verification_events", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_verification_events_tenant_id", table_name="tenant_verification_events"
    )
    op.drop_table("tenant_verification_events")

    # Restored with its original default. Any badge granted since the upgrade is
    # lost here, which is the honest outcome: the boolean cannot carry the
    # provenance the CHECK required, and inventing `is_verified = true` without
    # it would recreate the exact state this revision made unrepresentable.
    op.add_column(
        "tenants",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.drop_constraint("ck_tenants_verified_has_evidence", "tenants", type_="check")
    op.drop_constraint("fk_tenants_verified_by_users", "tenants", type_="foreignkey")
    op.drop_column("tenants", "verification_note")
    op.drop_column("tenants", "verified_by")
    op.drop_column("tenants", "verified_at")

    op.drop_column("users", "is_staff")
