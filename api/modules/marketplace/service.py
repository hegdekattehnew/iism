"""Business logic for the marketplace module.

Pure CRUD and querying (ADR-001 marketplace layer). No scoring happens here —
that belongs to the intelligence layer and arrives in a later sprint.
"""

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from api.modules.marketplace.models import Course, CourseSkill, Job, JobSkill
from api.modules.skills.models import Skill

PUBLISHED = "published"


def _text_filter(stmt: Select, model: type[Job] | type[Course], q: str) -> Select:
    """Full text across both languages, with a plain ILIKE fallback.

    The `simple` half of the vector carries Hindi, which has no stemmer, so a
    short Devanagari query can miss; ILIKE on the titles catches those.
    """
    like = f"%{q.lower()}%"
    return stmt.where(
        or_(
            model.search_vector.op("@@")(func.websearch_to_tsquery("english", q)),
            model.search_vector.op("@@")(func.websearch_to_tsquery("simple", q)),
            func.lower(model.title_en).like(like),
            func.lower(func.coalesce(model.title_hi, "")).like(like),
        )
    )


async def _paged(
    db: AsyncSession,
    stmt: Select,
    order: InstrumentedAttribute[str],
    limit: int,
    offset: int,
) -> tuple[list, int]:
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.scalars(stmt.order_by(order).limit(limit).offset(offset))
    return list(rows.unique()), total


# ----------------------------------------------------------------------- jobs


async def list_jobs(
    db: AsyncSession,
    *,
    q: str | None = None,
    skill_slug: str | None = None,
    location_state: str | None = None,
    employment_type: str | None = None,
    nsqf_level_max: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Job], int]:
    stmt = select(Job).where(Job.status == PUBLISHED)

    if q:
        stmt = _text_filter(stmt, Job, q)
    if skill_slug:
        stmt = stmt.where(
            Job.id.in_(
                select(JobSkill.job_id)
                .join(Skill, Skill.id == JobSkill.skill_id)
                .where(Skill.slug == skill_slug)
            )
        )
    if location_state:
        stmt = stmt.where(Job.location_state == location_state)
    if employment_type:
        stmt = stmt.where(Job.employment_type == employment_type)
    if nsqf_level_max is not None:
        stmt = stmt.where(or_(Job.nsqf_level_min.is_(None), Job.nsqf_level_min <= nsqf_level_max))

    return await _paged(db, stmt, Job.title_en, limit, offset)


async def get_job_by_slug(db: AsyncSession, slug: str) -> Job | None:
    return await db.scalar(select(Job).where(Job.slug == slug))


async def count_jobs(db: AsyncSession) -> int:
    return (
        await db.scalar(select(func.count()).select_from(Job).where(Job.status == PUBLISHED)) or 0
    )


async def jobs_requiring_skill(
    db: AsyncSession, skill_id: uuid.UUID, *, limit: int = 20
) -> list[Job]:
    """Powers the 'jobs needing this skill' section on a skill page.

    Mandatory requirements first — those are the ones that actually gate a hire.
    """
    stmt = (
        select(Job)
        .join(JobSkill, JobSkill.job_id == Job.id)
        .where(JobSkill.skill_id == skill_id, Job.status == PUBLISHED)
        .order_by(JobSkill.is_mandatory.desc(), JobSkill.importance.desc(), Job.title_en)
        .limit(limit)
    )
    return list((await db.scalars(stmt)).unique())


# -------------------------------------------------------------------- courses


async def list_courses(
    db: AsyncSession,
    *,
    q: str | None = None,
    skill_slug: str | None = None,
    mode: str | None = None,
    language: str | None = None,
    max_fee_inr: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Course], int]:
    stmt = select(Course).where(Course.status == PUBLISHED)

    if q:
        stmt = _text_filter(stmt, Course, q)
    if skill_slug:
        stmt = stmt.where(
            Course.id.in_(
                select(CourseSkill.course_id)
                .join(Skill, Skill.id == CourseSkill.skill_id)
                .where(Skill.slug == skill_slug)
            )
        )
    if mode:
        stmt = stmt.where(Course.mode == mode)
    if language:
        # 'both' satisfies a request for either single language.
        stmt = stmt.where(Course.language.in_([language, "both"]))
    if max_fee_inr is not None:
        stmt = stmt.where(or_(Course.fee_inr.is_(None), Course.fee_inr <= max_fee_inr))

    return await _paged(db, stmt, Course.title_en, limit, offset)


async def get_course_by_slug(db: AsyncSession, slug: str) -> Course | None:
    return await db.scalar(select(Course).where(Course.slug == slug))


async def count_courses(db: AsyncSession) -> int:
    return (
        await db.scalar(select(func.count()).select_from(Course).where(Course.status == PUBLISHED))
        or 0
    )


async def courses_teaching_skill(
    db: AsyncSession, skill_id: uuid.UUID, *, limit: int = 20
) -> list[Course]:
    """Powers 'courses teaching this skill'. Cheapest first — this cohort is
    price-sensitive, and fee is the most common reason a course is not taken."""
    stmt = (
        select(Course)
        .join(CourseSkill, CourseSkill.course_id == Course.id)
        .where(CourseSkill.skill_id == skill_id, Course.status == PUBLISHED)
        .order_by(Course.fee_inr.asc().nulls_last(), Course.title_en)
        .limit(limit)
    )
    return list((await db.scalars(stmt)).unique())
