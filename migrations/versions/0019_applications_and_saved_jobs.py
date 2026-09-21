"""Applications and saved jobs: the rows that let the loop close

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-17

Until now the product could compute an outcome and not produce one: no table
anywhere recorded that a candidate wanted a job, or that an employer had been
told who they were.

Both key on `candidate_profiles`, not `users`, and both cascade from it -- so
erasure (Sprint 20) takes applications and bookmarks with it without the
privacy module having to know these tables exist.

`contact_shared_at` / `contact_revoked_at` are the consent record for the one
disclosure this product makes: the candidate's name and contact reaching the
employer whose vacancy they applied to.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="applied"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("contact_shared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        # Named, every one: an unnamed constraint generates a downgrade that
        # calls drop_constraint(None, ...) and fails outright.
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_applications_job_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name="fk_applications_profile_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("job_id", "profile_id", name="uq_application_job_profile"),
        # Exactly what `one_of("status", APPLICATION_STATUSES)` generates in the
        # model. Alembic does not diff CHECK bodies, so the two are kept
        # byte-identical by hand and `tests/test_enumerations.py` compares them.
        # Byte-identical to what `one_of("status", APPLICATION_STATUSES)` puts in
        # the model. Alembic does not diff CHECK bodies, so drift here is
        # invisible; `tests/test_enumerations.py` is what compares them.
        sa.CheckConstraint("status IN ('applied', 'withdrawn', 'shortlisted', 'rejected', 'hired')", name="ck_application_status"),
    )
    op.create_index("ix_applications_job_id", "applications", ["job_id"])
    op.create_index("ix_applications_profile_id", "applications", ["profile_id"])

    op.create_table(
        "saved_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name="fk_saved_jobs_profile_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_saved_jobs_job_id", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("profile_id", "job_id", name="uq_saved_job"),
    )
    op.create_index("ix_saved_jobs_job_id", "saved_jobs", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_jobs_job_id", table_name="saved_jobs")
    op.drop_table("saved_jobs")
    op.drop_index("ix_applications_profile_id", table_name="applications")
    op.drop_index("ix_applications_job_id", table_name="applications")
    op.drop_table("applications")
