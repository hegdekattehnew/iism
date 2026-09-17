"""One table for every translation (ADR-041)

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-17

The table that lets a language be added with INSERTs instead of DDL. It is
created empty and stays empty until 0022 moves the ~95 Hindi values out of the
`_hi` columns -- which is the whole body of translated content in a ~600,000
row database.

`locale` has no CHECK, deliberately, while `entity_type`, `field` and `source`
all do: constraining it would put "add a language" back into a migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_translations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="human"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.UniqueConstraint(
            "entity_type", "entity_id", "field", "locale", name="uq_content_translation"
        ),
        # Byte-identical to what `one_of` generates in the model; Alembic does
        # not diff CHECK bodies, so `tests/test_enumerations.py` compares them.
        sa.CheckConstraint("entity_type IN ('skill', 'skill_concept', 'job', 'course', 'awarding_body', 'sector', 'sub_sector', 'occupation', 'qualification_pack', 'model_curriculum', 'performance_element', 'performance_criterion', 'knowledge_parameter', 'generic_criterion')", name="ck_content_translation_entity"),
        sa.CheckConstraint("field IN ('name', 'title', 'description', 'text', 'job_role')", name="ck_content_translation_field"),
        sa.CheckConstraint("source IN ('human', 'machine', 'imported')", name="ck_content_translation_source"),
    )
    op.create_index(
        "ix_content_translations_lookup",
        "content_translations",
        ["entity_type", "locale", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_translations_lookup", table_name="content_translations")
    op.drop_table("content_translations")
