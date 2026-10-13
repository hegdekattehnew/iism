"""A course has a place, a next intake and a number of seats

Revision ID: 0051
Revises: 0050
Create Date: 2026-10-13

Sprint 58 (BL-14.5, ADR-068). `courses_closing_gap` recommended an offline course in another state
exactly as it recommended one next door, because a course had no place at all. Six nullable columns,
nothing backfilled: a course published before this has no stated place, and inventing one would be
a factual claim the data does not support.

The two ids are `SET NULL` foreign keys beside the free text, as on `jobs`. `seats` is the number of
places the provider offers; **seats left is derived** from enrolled interests and never stored.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("location_state", sa.String(), nullable=True))
    op.add_column("courses", sa.Column("location_district", sa.String(), nullable=True))
    op.add_column("courses", sa.Column("state_id", sa.Uuid(), nullable=True))
    op.add_column("courses", sa.Column("district_id", sa.Uuid(), nullable=True))
    op.add_column("courses", sa.Column("starts_on", sa.Date(), nullable=True))
    op.add_column("courses", sa.Column("seats", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_courses_state_id_states", "courses", "states", ["state_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_courses_district_id_districts",
        "courses",
        "districts",
        ["district_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_courses_state_id", "courses", ["state_id"])
    op.create_index("ix_courses_district_id", "courses", ["district_id"])
    op.create_check_constraint("ck_courses_seats", "courses", "seats IS NULL OR seats >= 1")


def downgrade() -> None:
    op.drop_constraint("ck_courses_seats", "courses", type_="check")
    op.drop_index("ix_courses_district_id", table_name="courses")
    op.drop_index("ix_courses_state_id", table_name="courses")
    op.drop_constraint("fk_courses_district_id_districts", "courses", type_="foreignkey")
    op.drop_constraint("fk_courses_state_id_states", "courses", type_="foreignkey")
    for column in (
        "seats",
        "starts_on",
        "district_id",
        "state_id",
        "location_district",
        "location_state",
    ):
        op.drop_column("courses", column)
