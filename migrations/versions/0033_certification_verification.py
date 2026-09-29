"""A verified certificate can set source='certified'

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-26

Sprint 35, BL-3.2. `docs/scope-reconciliation.md` postscript: `certified` has
had no writer outside `scripts/seed_candidates.py` since Sprint 4, so
`EVIDENCE_WEIGHT_SHARE` was a constant 0.6-floor for every real candidate.
`CandidateCertification.skill_id` has named the intended mechanism since
Sprint 5's own docstring; this gives it one.

Denormalised onto the row alone, deliberately simpler than
`tenant_verification_events` (0028): a candidate's own certification is
theirs to edit or delete at any time, unlike an organisation's badge, which
only an operator can touch -- there is no symmetrical need for an
append-only history an operator must consult before acting. The evidence
CHECK is the same shape as 0028's for that reason: a badge with no evidence
must not be representable, whichever table it lives on.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_certifications",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("candidate_certifications", sa.Column("verified_by", sa.Uuid(), nullable=True))
    op.add_column(
        "candidate_certifications", sa.Column("verification_note", sa.Text(), nullable=True)
    )
    op.create_foreign_key(
        "fk_candidate_certifications_verified_by_users",
        "candidate_certifications",
        "users",
        ["verified_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_candidate_certifications_verified_has_evidence",
        "candidate_certifications",
        "verified_at IS NULL OR ("
        "verified_by IS NOT NULL AND length(btrim(verification_note)) >= 10)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_candidate_certifications_verified_has_evidence",
        "candidate_certifications",
        type_="check",
    )
    op.drop_constraint(
        "fk_candidate_certifications_verified_by_users",
        "candidate_certifications",
        type_="foreignkey",
    )
    op.drop_column("candidate_certifications", "verification_note")
    op.drop_column("candidate_certifications", "verified_by")
    op.drop_column("candidate_certifications", "verified_at")
