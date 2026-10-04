"""An operator may edit role aliases, and the table is their source of truth

Revision ID: 0046
Revises: 0045
Create Date: 2026-10-04

Sprint 47, BL-12.15 (ADR-054). Role-alias coverage is the product's weakest point (43
roles of 3,417) and the people who could fix it -- somebody who knows the labour market --
could not, because an alias lived in a Python dict that `scripts/seed_skills.py` used to
project into this table by **deleting every row and rewriting it**. Anything added any
other way vanished at the next seed.

* `source` says who owns a row: `seed` rows are the dict's, `operator` rows are never
  touched by the seed. Every existing row is a seed row.
* `retired_at` is a soft delete, so a seed that still names a key cannot bring back an
  alias an operator withdrew. Role search ignores retired rows.
* `created_at` so the screen can say how old an alias is.
* `role_alias_events` is the audit record: edits are no longer in version control the way
  the dict was. It **names** the alias (a copy of key and target) rather than referencing
  it, because the seed may delete the row an event describes.

Both CHECKs are hand-written with frozen value tuples, because Alembic does not diff
CHECK bodies and a migration describes one moment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.database import one_of

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCES = ("seed", "operator")
_ACTIONS = ("added", "retired")


def upgrade() -> None:
    op.add_column(
        "role_aliases", sa.Column("source", sa.String(), server_default="seed", nullable=False)
    )
    op.add_column("role_aliases", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "role_aliases",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_check_constraint("ck_role_alias_source", "role_aliases", one_of("source", _SOURCES))

    op.create_table(
        "role_alias_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("surface_form", sa.Text(), nullable=False),
        sa.Column("job_role", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(one_of("action", _ACTIONS), name="ck_role_alias_event_action"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_role_alias_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_role_alias_events_created_at", "role_alias_events", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_role_alias_events_created_at", table_name="role_alias_events")
    op.drop_table("role_alias_events")
    # An operator's rows have no home in the old shape, where the seed owned the table.
    op.execute("DELETE FROM role_aliases WHERE source = 'operator'")
    op.drop_constraint("ck_role_alias_source", "role_aliases", type_="check")
    op.drop_column("role_aliases", "created_at")
    op.drop_column("role_aliases", "retired_at")
    op.drop_column("role_aliases", "source")
