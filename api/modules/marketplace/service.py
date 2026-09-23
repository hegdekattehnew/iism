"""Business logic for the marketplace module.

Pure CRUD and querying (ADR-001 marketplace layer). No scoring happens here —
that belongs to the intelligence layer and arrives in a later sprint.
"""

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from api.core.localisation import ContentTranslation
from api.modules.marketplace.models import Course, CourseSkill, Job, JobSkill, open_job
from api.modules.skills.models import Skill

PUBLISHED = "published"


def _text_filter(stmt: Select, model: type[Job] | type[Course], q: str) -> Select:
    """Full text over the source title, plus any language it was translated into.

    The vector covers the row's own text in both configurations -- Postgres has
    no Hindi stemmer, so a short Devanagari query can still miss it, and the
    ILIKE catches those. Translations live in their own table since ADR-041, so
    a title translated into a language the row was not written in is matched by
    the subquery rather than by a second column.
    """
    like = f"%{q.lower()}%"
    entity_type = "job" if model is Job else "course"
    return stmt.where(
        or_(
            model.search_vector.op("@@")(func.websearch_to_tsquery("english", q)),
            model.search_vector.op("@@")(func.websearch_to_tsquery("simple", q)),
            func.lower(model.title).like(like),
            model.id.in_(
                select(ContentTranslation.entity_id).where(
                    ContentTranslation.entity_type == entity_type,
                    ContentTranslation.field.in_(("title", "description")),
                    func.lower(ContentTranslation.text).like(like),
                )
            ),
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
    stmt = select(Job).where(open_job())

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

    return await _paged(db, stmt, Job.title, limit, offset)


async def get_job_by_slug(db: AsyncSession, slug: str) -> Job | None:
    """The **public** detail view: published only.

    Without the status filter a draft was readable by anyone holding the URL --
    200 on a listing its owner had not finished, and on one they had
    deliberately unpublished. Every other public query here filters; these two
    did not, and the tests only ever asserted the *list*, which is why it
    survived. The owner's own view goes through `job_publishing.get_job`,
    which is scoped to their tenant and shows drafts on purpose.
    """
    # **Not** `open_job()`. A closed vacancy keeps its page: people have
    # it bookmarked, it is in their application list, and a 404 on a row we
    # deliberately kept would be a broken link of our own making -- the same
    # rule retired skills follow. The page says it is closed; `is_open` on
    # the payload is what the client renders that from.
    return await db.scalar(select(Job).where(Job.slug == slug, Job.status == PUBLISHED))


async def count_jobs(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Job).where(open_job())) or 0


async def jobs_requiring_skill(
    db: AsyncSession, skill_id: uuid.UUID, *, limit: int = 20
) -> list[Job]:
    """Powers the 'jobs needing this skill' section on a skill page.

    Mandatory requirements first — those are the ones that actually gate a hire.
    """
    stmt = (
        select(Job)
        .join(JobSkill, JobSkill.job_id == Job.id)
        .where(JobSkill.skill_id == skill_id, open_job())
        .order_by(JobSkill.is_mandatory.desc(), JobSkill.importance.desc(), Job.title)
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

    return await _paged(db, stmt, Course.title, limit, offset)


async def get_course_by_slug(db: AsyncSession, slug: str) -> Course | None:
    """The **public** detail view: published only.

    Without the status filter a draft was readable by anyone holding the URL --
    200 on a listing its owner had not finished, and on one they had
    deliberately unpublished. Every other public query here filters; these two
    did not, and the tests only ever asserted the *list*, which is why it
    survived. The owner's own view goes through `course_publishing.get_course`,
    which is scoped to their tenant and shows drafts on purpose.
    """
    return await db.scalar(select(Course).where(Course.slug == slug, Course.status == PUBLISHED))


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
        .order_by(Course.fee_inr.asc().nulls_last(), Course.title)
        .limit(limit)
    )
    return list((await db.scalars(stmt)).unique())
