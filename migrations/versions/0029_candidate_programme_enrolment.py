"""Candidate programme enrolment

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-25

Sprint 33, BL-7.1. The government-agency actor's thin slice: a bulk-enrolled
candidate carries the name of the programme they were enrolled under, and
every self-registered candidate carries NULL. One nullable column rather than
a lookup table -- a programme is named ad hoc by whoever runs
`scripts/bulk_enrol_candidates.py`, has exactly one write path, and never
needs attributes of its own. Indexed because the programme report
(`operations.service.programme_report`) filters on it directly.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles", sa.Column("enrolled_via_programme", sa.String(), nullable=True)
    )
    op.create_index(
        "ix_candidate_profiles_enrolled_via_programme",
        "candidate_profiles",
        ["enrolled_via_programme"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_profiles_enrolled_via_programme", table_name="candidate_profiles")
    op.drop_column("candidate_profiles", "enrolled_via_programme")
