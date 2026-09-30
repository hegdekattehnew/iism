"""Semantic-similarity embedding columns on qualification_packs

Revision ID: 0040
Revises: 0039
Create Date: 2026-09-30

Sprint 40, foundation only. Same shape migration 0034 already used for
`jobs`/`candidate_profiles` -- ADR-013/031 fix the dimension at 384 regardless
of which model produces the vector, and NULL means "needs (re)computing," the
same convention `_EmbeddingColumns` documents for those two tables.

No backfill: every existing qualification pack gets NULL. Nothing reads this
column yet -- `refresh_role_embeddings` (the sweep that fills it in) and
`search_roles()`'s semantic tier are the next stories to land on top of this.
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "qualification_packs",
        sa.Column("embedding", pgvector.sqlalchemy.Vector(384), nullable=True),
    )
    op.add_column(
        "qualification_packs", sa.Column("embedding_provider", sa.String(), nullable=True)
    )
    op.add_column("qualification_packs", sa.Column("embedding_model", sa.String(), nullable=True))
    op.add_column(
        "qualification_packs",
        sa.Column("embedding_computed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("qualification_packs", "embedding_computed_at")
    op.drop_column("qualification_packs", "embedding_model")
    op.drop_column("qualification_packs", "embedding_provider")
    op.drop_column("qualification_packs", "embedding")
