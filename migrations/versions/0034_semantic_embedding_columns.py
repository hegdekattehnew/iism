"""Semantic-similarity embedding columns on jobs and candidate_profiles

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-27

Sprint 36, BL-5.1. pgvector has been enabled since 0001 with nothing stored in
it (`docs/IISM-High-Level-Design.docx` §4.2). ADR-013/031 fix the dimension at
384 regardless of which model eventually produces the vector, so the column
is sized for that from the start.

No backfill: every existing job and profile gets NULL, which is this
column's own "needs (re)computing" signal (see `_EmbeddingColumns`'s
docstring in `api/modules/marketplace/models.py`) -- the worker sweep fills
every row in on its first run rather than this migration fabricating vectors
for content it did not embed.
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("jobs", "candidate_profiles")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=True))
        op.add_column(table, sa.Column("embedding_provider", sa.String(), nullable=True))
        op.add_column(table, sa.Column("embedding_model", sa.String(), nullable=True))
        op.add_column(
            table,
            sa.Column("embedding_computed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "embedding_computed_at")
        op.drop_column(table, "embedding_model")
        op.drop_column(table, "embedding_provider")
        op.drop_column(table, "embedding")
