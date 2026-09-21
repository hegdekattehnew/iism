"""Role search: a trigram index on job_role, and two analytics names

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-18

Sprint 23 lets a candidate name their job role and be offered the standards of
the qualification behind it. Every one of the 4,424 qualification packs carries
a `job_role`; nothing indexed it, because nothing searched it.

**One GIN trigram index serves every branch of the search** -- `LIKE 'x%'`,
`LIKE '%x%'`, `%` and `<%` alike. Created with `op.execute`, so it is invisible
to SQLAlchemy's metadata and is listed in `MANUALLY_MANAGED_INDEXES`.

**The analytics CHECK is rewritten by hand**, as in 0020: Alembic does not diff
CHECK bodies, and `record()` swallows its own failures, so a name added to
`EVENT_NAMES` alone would produce events that silently never appear.

The names are frozen here rather than imported from the model. A migration
describes one moment; importing the live tuple would make this revision
produce a wider constraint the day a later sprint adds a name.
"""

from collections.abc import Sequence

from alembic import op

from api.core.database import one_of

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = (
    "matches_viewed",
    "match_opened",
    "gap_viewed",
    "course_recommended",
    "course_opened",
    "employer_overview_viewed",
    "employer_shortlist_viewed",
    "application_submitted",
    "application_withdrawn",
    "application_status_changed",
    "job_saved",
)
_ADDED = ("role_suggested", "skills_bulk_added")


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_qualification_packs_job_role_trgm "
        "ON qualification_packs USING gin (lower(job_role) gin_trgm_ops)"
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _BEFORE + _ADDED)
    )


def downgrade() -> None:
    # Rows carrying a name the narrower constraint forbids would block it.
    op.execute(
        "DELETE FROM analytics_events WHERE name IN ('role_suggested', 'skills_bulk_added')"
    )
    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint(
        "ck_analytics_event_name", "analytics_events", one_of("name", _BEFORE)
    )
    op.execute("DROP INDEX IF EXISTS ix_qualification_packs_job_role_trgm")
