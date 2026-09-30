"""role_aliases: a lay term resolved onto a qualification's job_role

Revision ID: 0039
Revises: 0038
Create Date: 2026-09-30

Moves `role_aliases.py`'s `ROLE_ALIASES` dict from a Python literal consulted
by `_ROLE_SEARCH_SQL` via `unnest()` arrays built in Python, to a table
`_ROLE_SEARCH_SQL` joins against directly -- the same shape `skill_aliases`
already is for `SkillAlias` (migration 0002). `role_aliases.py`'s dict stays
the authored source of truth; `scripts/seed_skills.py` replaces this table's
rows from it on every run, exactly as it already does for `skill_aliases`.

No foreign key to `qualification_packs`: `job_role` is free text matched
case-insensitively, because one role name spans multiple QP rows (reissues,
`-SI` variants) and the search query's own ranking picks the representative
one at read time -- the dict-based version worked the same way.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("surface_form", sa.Text(), nullable=False),
        sa.Column("job_role", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("surface_form", name="uq_role_alias_surface_form"),
    )


def downgrade() -> None:
    op.drop_table("role_aliases")
