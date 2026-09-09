"""Training providers writing their own listings.

The other half of ADR-026's "operations-curated seeding alongside provider
self-serve publishing". The jobs half shipped in Sprint 12; until now a
`course_provider` tenant could be created, could edit its own profile, and could
do nothing else — every write path in `api/` was jobs-only.

Deliberately a sibling of `publishing.py` rather than a generalisation of it.
The two share a shape and not a schema, and the differences are the interesting
part:

* a `JobSkill` carries `importance` and `is_mandatory`, because a match is
  scored against them; a `CourseSkill` carries only `level_taught`, because what
  matters about a course is whether it closes a gap and how far;
* duplicates therefore collapse on the **highest level taught**, not on the
  strongest signal — the seed's own rule, since a course covering a standard to
  level 4 in one module and level 3 in another does take the learner to 4;
* a course has no location at all, so none of the geography resolution jobs need.

What is identical, and identical on purpose: full replacement of the link rows
rather than a diff, an explicit `draft` on create, and a refusal to publish with
nothing attached.
"""

import uuid
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.modules.marketplace.listings import (
    load_with_skills,
    resolve_standards,
    unique_slug,
)
from api.modules.marketplace.models import Course, CourseSkill
from api.modules.marketplace.schemas import CourseIn, CourseSkillIn

# Copied field by field rather than `model_dump()`ed, so `search_vector` --
# GENERATED ALWAYS, and rejected by Postgres on any write -- can never reach an
# INSERT by way of a schema someone later widened.
_PLAIN_FIELDS = (
    "title_en",
    "title_hi",
    "description_en",
    "description_hi",
    "mode",
    "language",
    "duration_hours",
    "fee_inr",
    "nsqf_level",
)


async def _resolve_skills(
    db: AsyncSession, rows: list[CourseSkillIn]
) -> list[tuple[uuid.UUID, float | None]]:
    """Collapsed on the **highest level taught** — the opposite of a job's merge,
    and the seed's own rule: a course covering a standard to level 4 in one
    module and level 3 in another does take the learner to 4.

    The existence and retired-row checks are shared with the vacancy surface
    (`listings.resolve_standards`), because that is validation policy and
    ADR-026 requires both paths to apply the same rules.
    """
    if not rows:
        return []
    ids = await resolve_standards(db, [r.skill_slug for r in rows], verb="taught")

    taught: dict[uuid.UUID, float | None] = {}
    for row in rows:
        skill_id = ids[row.skill_slug]
        current = taught.get(skill_id)
        if skill_id not in taught or (row.level_taught or 0) > (current or 0):
            taught[skill_id] = row.level_taught
    return list(taught.items())


async def _write_skills(db: AsyncSession, course: Course, rows: list[CourseSkillIn]) -> None:
    resolved = await _resolve_skills(db, rows)
    await db.execute(delete(CourseSkill).where(CourseSkill.course_id == course.id))
    for skill_id, level in resolved:
        db.add(CourseSkill(course_id=course.id, skill_id=skill_id, level_taught=level))
    await db.flush()


async def _load(db: AsyncSession, course_id: uuid.UUID) -> Course:
    return cast(Course, await load_with_skills(db, Course, CourseSkill, course_id, label="Course"))


async def list_courses(db: AsyncSession, tenant_id: uuid.UUID) -> list[Course]:
    """This provider's listings, drafts included."""
    return list(
        (
            await db.scalars(
                select(Course)
                .where(Course.tenant_id == tenant_id)
                .options(
                    selectinload(Course.skills).selectinload(CourseSkill.skill),
                    selectinload(Course.tenant),
                )
                .order_by(Course.updated_at.desc())
            )
        ).all()
    )


async def get_course(db: AsyncSession, tenant_id: uuid.UUID, slug: str) -> Course:
    """404, never 403, on someone else's listing — a 403 confirms it exists."""
    course = await db.scalar(
        select(Course).where(Course.slug == slug, Course.tenant_id == tenant_id)
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return await _load(db, course.id)


async def create_course(db: AsyncSession, tenant_id: uuid.UUID, payload: CourseIn) -> Course:
    course = Course(
        slug=await unique_slug(db, Course.slug, payload.title_en),
        tenant_id=tenant_id,
        # Explicit. `Course.status` defaults to "published" at the model level,
        # so omitting this would put an unfinished syllabus in front of
        # candidates. The seed sets `published` on purpose; a form must not.
        status="draft",
        **{f: getattr(payload, f) for f in _PLAIN_FIELDS},
    )
    db.add(course)
    await db.flush()
    await _write_skills(db, course, payload.skills)
    await db.commit()
    return await _load(db, course.id)


async def update_course(
    db: AsyncSession, tenant_id: uuid.UUID, slug: str, payload: CourseIn
) -> Course:
    course = await db.scalar(
        select(Course).where(Course.slug == slug, Course.tenant_id == tenant_id)
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")

    for field in _PLAIN_FIELDS:
        setattr(course, field, getattr(payload, field))
    # The slug is not regenerated: it is a published URL as soon as the course
    # goes live, and rewriting it on a title tweak breaks every link to it.
    await db.flush()
    await _write_skills(db, course, payload.skills)
    await db.commit()
    return await _load(db, course.id)


async def set_published(
    db: AsyncSession, tenant_id: uuid.UUID, slug: str, published: bool
) -> Course:
    course = await db.scalar(
        select(Course).where(Course.slug == slug, Course.tenant_id == tenant_id)
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")

    if published:
        teaches = await db.scalar(
            select(CourseSkill.id).where(CourseSkill.course_id == course.id).limit(1)
        )
        if teaches is None:
            # `courses_closing_gap` inner-joins `CourseSkill`, so a course
            # teaching nothing can never be recommended to anyone. It would be
            # published and permanently unreachable.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Add at least one standard this course teaches before publishing",
            )

    course.status = "published" if published else "draft"
    await db.commit()
    return await _load(db, course.id)


async def delete_course(db: AsyncSession, tenant_id: uuid.UUID, slug: str) -> None:
    course = await db.scalar(
        select(Course).where(Course.slug == slug, Course.tenant_id == tenant_id)
    )
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    await db.delete(course)
    await db.commit()
