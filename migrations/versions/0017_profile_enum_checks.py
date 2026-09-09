"""Back the last two closed sets on candidate_profiles with CHECKs

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-09

Written by hand: **Alembic does not diff CHECK constraint bodies**, so neither
their absence nor their contents is something autogenerate will ever mention.

`education_level` and `preferred_employment_type` are typed as closed `Literal`
unions on `CandidateProfileFull`, which is a *response* model. The convention is
that output schemas stay permissive precisely because one out-of-range row 500s
the entire response -- so a closed union on the way out is only safe while the
column cannot hold anything else. These two could: every sibling enum on the
table was constrained and these two were missed, which is also why
`EDUCATION_LEVELS` sat exported and read by nothing.

Nullable on both sides: an unstated education level is not an invalid one, and
the columns are optional by design (DPDP -- nothing on this table is required).
Verified against the live database before writing: 5 profiles carry a level, 1
carries a preferred type, and every value is already in range.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EDUCATION = (
    "education_level IS NULL OR education_level IN ('none', 'primary', 'secondary', "
    "'higher_secondary', 'iti', 'diploma', 'graduate', 'postgraduate')"
)
_EMPLOYMENT = (
    "preferred_employment_type IS NULL OR preferred_employment_type IN "
    "('full_time', 'part_time', 'contract', 'apprenticeship')"
)


def upgrade() -> None:
    op.create_check_constraint("ck_candidate_education_level", "candidate_profiles", _EDUCATION)
    op.create_check_constraint(
        "ck_candidate_preferred_employment", "candidate_profiles", _EMPLOYMENT
    )


def downgrade() -> None:
    op.drop_constraint("ck_candidate_preferred_employment", "candidate_profiles", type_="check")
    op.drop_constraint("ck_candidate_education_level", "candidate_profiles", type_="check")
