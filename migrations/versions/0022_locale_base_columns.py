"""Source text in the base column; Hindi moves to content_translations (ADR-041)

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-17

Renames 18 `_en` columns across 14 tables to the bare field name, moves every
`_hi` value into `content_translations`, and drops the `_hi` columns.

**The generated search vectors are the hazard.** `skills`, `jobs` and `courses`
each carry a `search_vector` GENERATED over four of the columns involved, so
Postgres refuses to drop those columns while the expression depends on them.
Each vector is therefore dropped, the columns changed, and the vector rebuilt --
over the source column only, since translations now live in their own table and
are searched through it.

The rebuilt vector indexes the source column with **both** the `english` and
`simple` configurations. Before this migration the two halves meant "English
column" and "Hindi column"; now a single column may hold either, because
`source_locale` says what language a job was written in. Postgres ships no
Hindi stemmer (ADR-033 qualifying ADR-021), so `simple` is what keeps
Devanagari matchable.

Rehearsed against a full copy of the development database before being applied
to it -- 600,000 rows, three generated columns and a trigram index is not a
migration to meet for the first time in anger.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, entity_type, [(old_en_column, new_column, translation_field)], has_hi)
TABLES: list[tuple[str, str, list[tuple[str, str, str]], bool]] = [
    ("awarding_bodies", "awarding_body", [("name_en", "name", "name")], True),
    (
        "courses",
        "course",
        [("title_en", "title", "title"), ("description_en", "description", "description")],
        True,
    ),
    (
        "jobs",
        "job",
        [("title_en", "title", "title"), ("description_en", "description", "description")],
        True,
    ),
    # No `_hi` half was ever added here.
    ("model_curricula", "model_curriculum", [("job_role_en", "job_role", "job_role")], False),
    ("occupations", "occupation", [("name_en", "name", "name")], True),
    (
        "qualification_packs",
        "qualification_pack",
        [("name_en", "name", "name"), ("job_role_en", "job_role", "job_role")],
        True,
    ),
    ("sectors", "sector", [("name_en", "name", "name")], True),
    ("skill_concepts", "skill_concept", [("name_en", "name", "name")], True),
    ("skill_generic_criteria", "generic_criterion", [("text_en", "text", "text")], True),
    ("skill_knowledge_params", "knowledge_parameter", [("text_en", "text", "text")], True),
    (
        "skill_performance_criteria",
        "performance_criterion",
        [("description_en", "description", "description")],
        True,
    ),
    ("skill_performance_elements", "performance_element", [("name_en", "name", "name")], True),
    (
        "skills",
        "skill",
        [("name_en", "name", "name"), ("description_en", "description", "description")],
        True,
    ),
    ("sub_sectors", "sub_sector", [("name_en", "name", "name")], True),
]

# The tables whose search_vector must be dropped before their columns can be.
VECTORS = {
    "skills": ("ix_skills_search_vector", "name", "description"),
    "jobs": ("ix_jobs_search_vector", "title", "description"),
    "courses": ("ix_courses_search_vector", "title", "description"),
}


def _tsv(primary: str, secondary: str) -> str:
    """The vector over source text, in both configurations.

    Both, because one column may now hold English or Hindi -- which is exactly
    what `source_locale` records.
    """
    return (
        f"setweight(to_tsvector('english', coalesce({primary}, '')), 'A') || "
        f"setweight(to_tsvector('simple',  coalesce({primary}, '')), 'A') || "
        f"setweight(to_tsvector('english', coalesce({secondary}, '')), 'C') || "
        f"setweight(to_tsvector('simple',  coalesce({secondary}, '')), 'C')"
    )


def upgrade() -> None:
    # 1. The generated vectors depend on the columns about to change.
    for table in VECTORS:
        op.execute(f"ALTER TABLE {table} DROP COLUMN search_vector")
    # Built on lower(name_en); the rename would leave the index correct but
    # misleadingly named, and the name is what `MANUALLY_MANAGED_INDEXES` keys on.
    op.execute("DROP INDEX IF EXISTS ix_skills_name_en_trgm")

    for table, entity_type, columns, has_hi in TABLES:
        for old, new, field in columns:
            # 2. Carry the Hindi text out before the column holding it goes.
            #    Empty strings are not translations; they are absent values that
            #    would otherwise become rows claiming Hindi exists.
            if has_hi:
                hi_column = old.replace("_en", "_hi")
                op.execute(
                    f"""
                    INSERT INTO content_translations
                        (id, entity_type, entity_id, field, locale, text, source)
                    SELECT gen_random_uuid(), '{entity_type}', id, '{field}', 'hi',
                           {hi_column}, 'imported'
                    FROM {table}
                    WHERE {hi_column} IS NOT NULL AND btrim({hi_column}) <> ''
                    """
                )
                op.execute(f"ALTER TABLE {table} DROP COLUMN {hi_column}")
            # 3. The base column becomes the field itself.
            op.alter_column(table, old, new_column_name=new)

    # 4. Author-written content can be written in any language; the corpus is
    #    published in English and says so by omission.
    for table in ("jobs", "courses"):
        op.add_column(
            table,
            sa.Column("source_locale", sa.String(), nullable=False, server_default="en"),
        )

    # 5. Rebuild what step 1 removed, over the new column names.
    for table, (index_name, primary, secondary) in VECTORS.items():
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN search_vector tsvector "
            f"GENERATED ALWAYS AS ({_tsv(primary, secondary)}) STORED"
        )
        op.execute(f"CREATE INDEX {index_name} ON {table} USING gin (search_vector)")
    op.execute("CREATE INDEX ix_skills_name_trgm ON skills USING gin (lower(name) gin_trgm_ops)")


def downgrade() -> None:
    for table in VECTORS:
        op.execute(f"ALTER TABLE {table} DROP COLUMN search_vector")
    op.execute("DROP INDEX IF EXISTS ix_skills_name_trgm")

    for table in ("jobs", "courses"):
        op.drop_column(table, "source_locale")

    for table, entity_type, columns, has_hi in TABLES:
        for old, new, field in columns:
            op.alter_column(table, new, new_column_name=old)
            if has_hi:
                hi_column = old.replace("_en", "_hi")
                op.add_column(table, sa.Column(hi_column, sa.String(), nullable=True))
                op.execute(
                    f"""
                    UPDATE {table} t
                    SET {hi_column} = ct.text
                    FROM content_translations ct
                    WHERE ct.entity_type = '{entity_type}'
                      AND ct.entity_id = t.id
                      AND ct.field = '{field}'
                      AND ct.locale = 'hi'
                    """
                )
                op.execute(
                    f"DELETE FROM content_translations "
                    f"WHERE entity_type = '{entity_type}' AND field = '{field}' AND locale = 'hi'"
                )

    # The pairs the old vector was built from, spelled out rather than derived:
    # a downgrade is read in an emergency, not puzzled over.
    old_columns = {
        "skills": ("name_en", "name_hi", "description_en", "description_hi"),
        "jobs": ("title_en", "title_hi", "description_en", "description_hi"),
        "courses": ("title_en", "title_hi", "description_en", "description_hi"),
    }
    for table, (index_name, _primary, _secondary) in VECTORS.items():
        a_en, a_hi, c_en, c_hi = old_columns[table]
        old_tsv = (
            f"setweight(to_tsvector('english', coalesce({a_en}, '')), 'A') || "
            f"setweight(to_tsvector('simple',  coalesce({a_hi}, '')), 'A') || "
            f"setweight(to_tsvector('english', coalesce({c_en}, '')), 'C') || "
            f"setweight(to_tsvector('simple',  coalesce({c_hi}, '')), 'C')"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN search_vector tsvector "
            f"GENERATED ALWAYS AS ({old_tsv}) STORED"
        )
        op.execute(f"CREATE INDEX {index_name} ON {table} USING gin (search_vector)")
    op.execute(
        "CREATE INDEX ix_skills_name_en_trgm ON skills USING gin (lower(name_en) gin_trgm_ops)"
    )
