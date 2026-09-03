"""Extend skills, add aliases, and enable search

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Trigram matching carries fuzzy and partial-transliteration search. It also
    # compensates for Postgres shipping no Hindi stemmer or stopword list, which
    # limits what full-text search alone can do for Devanagari (ADR-021, ADR-033).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column("skills", sa.Column("name_hi", sa.String(), nullable=True))
    op.add_column("skills", sa.Column("description_en", sa.String(), nullable=True))
    op.add_column("skills", sa.Column("description_hi", sa.String(), nullable=True))
    op.add_column(
        "skills",
        sa.Column(
            "skill_type", sa.String(), nullable=False, server_default="technical"
        ),
    )
    op.add_column("skills", sa.Column("nsqf_level", sa.Integer(), nullable=True))

    op.create_check_constraint(
        "ck_skills_type", "skills", "skill_type IN ('technical', 'core', 'generic')"
    )
    op.create_check_constraint(
        "ck_skills_nsqf_level",
        "skills",
        "nsqf_level IS NULL OR (nsqf_level BETWEEN 1 AND 10)",
    )

    # Maintained by Postgres, never written by the application, so it can never
    # drift from the row it describes. English text is stemmed; Hindi uses
    # 'simple' because no Hindi configuration exists.
    op.execute(
        """
        ALTER TABLE skills ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(name_en, '')), 'A') ||
            setweight(to_tsvector('simple',  coalesce(name_hi, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description_en, '')), 'C') ||
            setweight(to_tsvector('simple',  coalesce(description_hi, '')), 'C')
        ) STORED
        """
    )
    op.execute("CREATE INDEX ix_skills_search_vector ON skills USING GIN (search_vector)")
    op.execute(
        "CREATE INDEX ix_skills_name_en_trgm ON skills "
        "USING GIN (lower(name_en) gin_trgm_ops)"
    )

    op.create_table(
        "skill_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("surface_form", sa.String(), nullable=False),
        sa.Column("script", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "surface_form", name="uq_alias_skill_form"),
        sa.CheckConstraint(
            "script IN ('latin', 'devanagari', 'transliteration')",
            name="ck_alias_script",
        ),
    )
    op.create_index("ix_skill_aliases_skill_id", "skill_aliases", ["skill_id"])
    op.execute(
        "CREATE INDEX ix_skill_aliases_form_trgm ON skill_aliases "
        "USING GIN (lower(surface_form) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_skill_aliases_form_trgm", table_name="skill_aliases")
    op.drop_index("ix_skill_aliases_skill_id", table_name="skill_aliases")
    op.drop_table("skill_aliases")

    op.drop_index("ix_skills_name_en_trgm", table_name="skills")
    op.drop_index("ix_skills_search_vector", table_name="skills")
    op.drop_column("skills", "search_vector")

    op.drop_constraint("ck_skills_nsqf_level", "skills", type_="check")
    op.drop_constraint("ck_skills_type", "skills", type_="check")
    op.drop_column("skills", "nsqf_level")
    op.drop_column("skills", "skill_type")
    op.drop_column("skills", "description_hi")
    op.drop_column("skills", "description_en")
    op.drop_column("skills", "name_hi")
    # pg_trgm is left installed: other schemas may depend on it.
