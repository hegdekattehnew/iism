"""Widen course_skills.level_taught to accept half-levels

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-04

Migration 0007 widened the four columns holding a *qualification's* level and
missed the one holding a level a course teaches a skill *to*. That was survivable
while courses pointed at 52 hand-written skills, every one of them at a whole
level. It stopped being survivable the moment 0008 imported the national corpus:
8,055 of 21,303 units now sit at a half-level, so a course could not record that
it teaches one of them to the level the qualification actually defines.

Same reasoning and same hand-written form as 0007 -- Alembic does not diff CHECK
constraint bodies, so widening one is invisible to --autogenerate.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_course_skill_level", "course_skills", type_="check")
    op.alter_column(
        "course_skills",
        "level_taught",
        existing_type=sa.Integer(),
        type_=sa.Numeric(3, 1),
        existing_nullable=True,
        postgresql_using="level_taught::numeric(3,1)",
    )
    op.create_check_constraint(
        "ck_course_skill_level",
        "course_skills",
        "level_taught IS NULL OR (level_taught >= 1 AND level_taught <= 10)",
    )


def downgrade() -> None:
    """Lossy, exactly as in 0007: a half-level cannot survive a round trip.

    ROUND() rather than a cast, so 4.5 becomes 5 instead of raising. Any course
    recorded against a half-level unit silently changes meaning -- which is the
    reason this direction exists only for local schema surgery.
    """
    op.drop_constraint("ck_course_skill_level", "course_skills", type_="check")
    op.alter_column(
        "course_skills",
        "level_taught",
        existing_type=sa.Numeric(3, 1),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="ROUND(level_taught)::integer",
    )
    op.create_check_constraint(
        "ck_course_skill_level",
        "course_skills",
        "level_taught IS NULL OR (level_taught BETWEEN 1 AND 10)",
    )
