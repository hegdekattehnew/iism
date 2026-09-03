"""Enable pgvector and create the skills table

Revision ID: 0001
Revises:
Create Date: 2026-09-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enabled now so no later migration has to; the extension is a prerequisite
    # for every embedding column added from Sprint 3 onward (ADR-003, ADR-013).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name_en", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_skills_slug"), "skills", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_skills_slug"), table_name="skills")
    op.drop_table("skills")
    # The extension is intentionally left in place: other schemas may rely on it.
