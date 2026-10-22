"""Business logic for the marketplace module.

Pure CRUD and querying (ADR-001 marketplace layer). No scoring happens here —
that belongs to the intelligence layer and arrives in a later sprint.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from api.core.localisation import ContentTranslation
from api.core.text import expand_query_terms
from api.modules.identity.models import Tenant
from api.modules.marketplace.models import (
    Course,
    CourseSkill,
    Job,
    JobSkill,
    open_job,
    posted_job,
)
from api.modules.skills import packs_by_code
from api.modules.skills.hierarchy import Sector
from api.modules.skills.models import Skill

PUBLISHED = "published"

_Order = ColumnElement[Any] | InstrumentedAttribute[Any]


def seats_left(seats: int | None, enrolled: int) -> int | None:
    """Places left on a course, or `None` when the provider gave no seat count.

    Never negative: a provider may mark more learners enrolled than they said they had room for,
    and "-2 seats left" is a number nobody can act on.
    """
    return None if seats is None else max(0, seats - enrolled)


async def seats_left_for(
    db: AsyncSession, courses: Sequence[Course]
) -> dict[uuid.UUID, int | None]:
    """Seats left for each course, in one grouped query for the ones that have a seat count."""
    # Function-level: `interests` imports this module, so the module-level form is a cycle.
    from api.modules.interests import enrolled_counts

    limited = [c for c in courses if c.seats is not None]
    enrolled = await enrolled_counts(db, [c.id for c in limited]) if limited else {}
    return {c.id: seats_left(c.seats, enrolled.get(c.id, 0)) for c in courses}


async def qualification_for(
    db: AsyncSession, courses: Sequence[Course]
) -> dict[uuid.UUID, dict[str, object]]:
    """What each course's `qualification_pack_code` stands for now, in one query (Sprint 75).

    Returned as the fields to `model_copy(update=...)` onto the payload, like seats left: read
    when shown and never stored, so a taxonomy re-import cannot leave a stale name or credit, and
    a pack that has gone shows nothing rather than something wrong.
    """
    facts = await packs_by_code(db, [c.qualification_pack_code for c in courses])
    out: dict[uuid.UUID, dict[str, object]] = {}
    for c in courses:
        fact = facts.get(c.qualification_pack_code or "")
        out[c.id] = (
            {"qualification_name": fact.job_role, "qualification_credits": fact.credits}
            if fact
            else {"qualification_name": None, "qualification_credits": None}
        )
    return out


def _text_filter(stmt: Select, model: type[Job] | type[Course], q: str) -> Select:
    """Full text over the source title, plus any language it was translated into.

    The vector covers the row's own text in both configurations -- Postgres has
    no Hindi stemmer, so a short Devanagari query can still miss it, and the
    ILIKE catches those. Translations live in their own table since ADR-041, so
    a title translated into a language the row was not written in is matched by
    the subquery rather than by a second column.

    Tried alongside every `WORD_SYNONYMS` expansion of `q` (`api/core/text.py`)
    -- "tech" alone never finds a real IT-sector listing, since none of their
    titles/descriptions contain that literal word, only "technology"/"IT-ITeS".
    One query, still: every variant folds into the same `or_(...)`, not a
    second round trip.
    """
    entity_type = "job" if model is Job else "course"
    conditions = []
    for term in expand_query_terms(q):
        like = f"%{term.lower()}%"
        conditions.extend(
            [
                model.search_vector.op("@@")(func.websearch_to_tsquery("english", term)),
                model.search_vector.op("@@")(func.websearch_to_tsquery("simple", term)),
                func.lower(model.title).like(like),
                model.id.in_(
                    select(ContentTranslation.entity_id).where(
                        ContentTranslation.entity_type == entity_type,
                        ContentTranslation.field.in_(("title", "description")),
                        func.lower(ContentTranslation.text).like(like),
                    )
                ),
            ]
        )
    return stmt.where(or_(*conditions))


async def _paged(
    db: AsyncSession,
    stmt: Select,
    order: Sequence[_Order],
    limit: int,
    offset: int,
) -> tuple[list, int]:
    """One page and the true total. **`order` must end in something unique** (the id): ordered by
    a title alone, two vacancies with the same title could swap places between page one and two."""
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.scalars(stmt.order_by(*order).limit(limit).offset(offset))
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
    sort: str = "title",
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

    if sort == "newest":
        # Newest posted first (Sprint 75). A vacancy published before `published_at` existed has no
        # date and sorts **after** every dated one, never by its draft's date, which would be the
        # invented posting date Sprint 74 refused to show.
        order: list[_Order] = [Job.published_at.desc().nulls_last(), Job.title, Job.id]
    else:
        order = [Job.title, Job.id]
    return await _paged(db, stmt, order, limit, offset)


async def job_states(db: AsyncSession) -> list[tuple[str, int]]:
    """Each state named by an open vacancy, with its count, in name order (Sprint 69, UI-06).

    The same `open_job()` predicate as the listing, so an option here always has a result behind
    it, and the figure beside it is the figure `/jobs?location_state=` will total.
    """
    rows = await db.execute(
        select(Job.location_state, func.count())
        .where(open_job(), Job.location_state.is_not(None), Job.location_state != "")
        .group_by(Job.location_state)
        .order_by(Job.location_state)
    )
    return [(name, count) for name, count in rows.all()]


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


async def count_jobs_posted(db: AsyncSession) -> int:
    """How many vacancies have been posted -- the homepage's headline figure.

    Two functions rather than one taking a flag, and **renamed** rather than
    redefined, so nothing that used to mean "open" quietly starts meaning
    "posted": every caller had to be revisited to compile.

    Two index-only counts where there was one. Both use the leading column of
    `ix_jobs_status_closed`, so the cost is the same shape as before. A single
    `count(*) FILTER (WHERE closed_at IS NULL)` would collapse them into one
    query -- and into one name, which is the thing being split here.
    """
    return await db.scalar(select(func.count()).select_from(Job).where(posted_job())) or 0


async def count_jobs_open(db: AsyncSession) -> int:
    """How many are still taking applications -- what `/jobs` will list."""
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
    tenant_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Course], int]:
    stmt = select(Course).where(Course.status == PUBLISHED)
    if tenant_id is not None:
        # One organisation's published courses (its public page, Sprint 94).
        stmt = stmt.where(Course.tenant_id == tenant_id)

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

    return await _paged(db, stmt, [Course.title, Course.id], limit, offset)


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


async def get_provider_by_slug(db: AsyncSession, slug: str) -> Tenant | None:
    """The **public** view of a training organisation (Sprint 94, ADR-102).

    Only a `course_provider` has a page: an employer's slug, a personal workspace's and a missing
    one are all the same 404, so this cannot be used to tell which slugs exist or what they are.
    Everything on the page is public by construction: it is built from `TenantOut`'s fields, the
    claims an organisation chose to make, and its published courses, never `contact_email`.
    """
    return await db.scalar(
        select(Tenant).where(Tenant.slug == slug, Tenant.tenant_type == "course_provider")
    )


async def provider_sectors(db: AsyncSession, tenant_id: uuid.UUID) -> list[tuple[str, int]]:
    """The sectors an organisation trains in, **read from its published courses, never stored**.

    A course teaches standards and a standard belongs to a sector, so the answer is derived each
    time: it cannot go stale when a course is unpublished or a standard moves, and an organisation
    cannot claim a sector it has no course in. Most courses first, then by name.
    """
    count = func.count(func.distinct(Course.id))
    rows = await db.execute(
        select(Sector.name, count)
        .select_from(Course)
        .join(CourseSkill, CourseSkill.course_id == Course.id)
        .join(Skill, Skill.id == CourseSkill.skill_id)
        .join(Sector, Sector.id == Skill.sector_id)
        .where(Course.tenant_id == tenant_id, Course.status == PUBLISHED)
        .group_by(Sector.name)
        .order_by(count.desc(), Sector.name)
    )
    return [(name, n) for name, n in rows.all()]
