"""Denormalise the qualification count onto skills

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-04

The skill browser has to order 21,303 rows to render its first page, and
alphabetical is the wrong order for a taxonomy this size: it opens on "0JT" and
"10.1. Case Studies" -- real records with real NOS codes, but the least
representative rows in the corpus.

Ordering by how many current qualifications use a unit puts the widely-required
units first, which is both a better answer and a useful signal to show on the
card. Counting per row would mean an ORDER BY over a correlated subquery, which
cannot use an index, so the count is denormalised here and maintained by the
importer in the same pass that derives the modal level.

Backfilled below so the column is correct immediately, without waiting for the
next import.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column("qp_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_skills_qp_count", "skills", ["qp_count"])

    # Backfill from the links that already exist. Only current qualifications
    # count -- a unit required solely by a superseded QP is not required today.
    op.execute(
        """
        UPDATE skills s
           SET qp_count = c.n
          FROM (
                SELECT q.skill_id, COUNT(*) AS n
                  FROM qp_skills q
                  JOIN qualification_packs p ON p.id = q.qp_id
                 WHERE p.is_current
              GROUP BY q.skill_id
               ) c
         WHERE c.skill_id = s.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_skills_qp_count", table_name="skills")
    op.drop_column("skills", "qp_count")
