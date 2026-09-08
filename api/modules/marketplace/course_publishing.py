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
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.text import slugify
from api.modules.marketplace.models import Course, CourseSkill
from api.modules.marketplace.schemas import CourseIn, CourseSkillIn
from api.modules.skills.models import Skill

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


async def _unique_slug(db: AsyncSession, title: str) -> str:
    """Title alone, unlike a job's title-and-district: a course has no location.

    A Hindi-only title transliterates to nothing, so there is a fallback.
    """
    base = slugify(title)[:80].strip("-") or "course"
    taken = set((await db.scalars(select(Course.slug).where(Course.slug.like(f"{base}%")))).all())
    if base not in taken:
        return base
    for n in range(2, 200):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    return f"{base}-{datetime.now(UTC).timestamp():.0f}"


async def _resolve_skills(
    db: AsyncSession, rows: list[CourseSkillIn]
) -> list[tuple[uuid.UUID, float | None]]:
    """Slugs to skill ids, collapsed on the highest level taught."""
    if not rows:
        return []

    slugs = [r.skill_slug for r in rows]
    found = {
        slug: (skill_id, source)
        for slug, skill_id, source in (
            await db.execute(
                select(Skill.slug, Skill.id, Skill.source).where(Skill.slug.in_(slugs))
            )
        ).all()
    }

    unknown = sorted(set(slugs) - found.keys())
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown standards: {', '.join(unknown)}",
        )
    # A retired row would make the course unmatchable: matching compares at
    # concept level over the national taxonomy, and `legacy` rows are excluded
    # from it.
    retired = sorted(s for s in slugs if found[s][1] == "legacy")
    if retired:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Retired standards cannot be taught: {', '.join(retired)}",
        )

    taught: dict[uuid.UUID, float | None] = {}
    for row in rows:
        skill_id = found[row.skill_slug][0]
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
    """Re-read with relationships populated.

    `populate_existing` because the instance is already in the identity map with
    a stale `skills` collection after the delete-and-rewrite above — without it
    the query succeeds and quietly returns the previous syllabus.
    """
    course = await db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.skills).selectinload(CourseSkill.skill),
            selectinload(Course.tenant),
        )
        .execution_options(populate_existing=True)
    )
    if course is None:  # pragma: no cover - just written
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return course


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
        slug=await _unique_slug(db, payload.title_en),
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
