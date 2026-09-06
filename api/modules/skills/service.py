"""Business logic for the skills module.

Routes validate and delegate here; they contain no logic themselves (CLAUDE.md).
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.skills.content import (
    GenericCriterion,
    KnowledgeParameter,
    PerformanceCriterion,
    PerformanceElement,
)
from api.modules.skills.hierarchy import QpSkill, QualificationPack, Sector
from api.modules.skills.models import Skill

MAX_SEARCH_RESULTS = 50

# One pass over both tables, scored so that a deliberate exact match always
# outranks a fuzzy one. Aliases are searched alongside canonical names, which is
# what lets transliterated Hindi input resolve to the right skill.
_SEARCH_SQL = text(
    """
WITH q AS (
    SELECT CAST(:raw AS text) AS raw, lower(trim(CAST(:raw AS text))) AS norm
),
matches AS (
    -- canonical names, exact then prefix
    SELECT s.id AS skill_id,
           CASE WHEN lower(s.name_en) = q.norm
                  OR lower(coalesce(s.name_hi, '')) = q.norm THEN 4.0
                ELSE 3.0 END AS score,
           s.name_en AS matched_on,
           CASE WHEN lower(s.name_en) = q.norm
                  OR lower(coalesce(s.name_hi, '')) = q.norm THEN 'exact'
                ELSE 'prefix' END AS match_kind
    FROM skills s, q
    WHERE lower(s.name_en) LIKE q.norm || '%'
       OR lower(coalesce(s.name_hi, '')) LIKE q.norm || '%'

    UNION ALL

    -- alias surface forms: latin, devanagari and transliteration alike
    SELECT a.skill_id,
           CASE WHEN lower(a.surface_form) = q.norm THEN 3.5
                WHEN lower(a.surface_form) LIKE q.norm || '%' THEN 2.5
                ELSE 1.8 END,
           a.surface_form,
           'alias'
    FROM skill_aliases a, q
    WHERE lower(a.surface_form) LIKE '%' || q.norm || '%'

    UNION ALL

    -- full text over names and descriptions; both configs, because the vector
    -- mixes english-stemmed and simple-tokenised text
    SELECT s.id,
           1.0 + ts_rank(s.search_vector, websearch_to_tsquery('english', q.raw)),
           s.name_en,
           'text'
    FROM skills s, q
    WHERE s.search_vector @@ websearch_to_tsquery('english', q.raw)
       OR s.search_vector @@ websearch_to_tsquery('simple', q.raw)

    UNION ALL

    -- trigram fallback: catches typos and partial transliterations
    SELECT a.skill_id,
           similarity(lower(a.surface_form), q.norm),
           a.surface_form,
           'alias'
    FROM skill_aliases a, q
    WHERE lower(a.surface_form) % q.norm
),
best AS (
    SELECT DISTINCT ON (skill_id) skill_id, score, matched_on, match_kind
    FROM matches
    ORDER BY skill_id, score DESC
)
SELECT b.skill_id, b.score, b.matched_on, b.match_kind
FROM best b
JOIN skills s ON s.id = b.skill_id
-- Retired vocabulary. The 52 curated skills were superseded by the national
-- standards they map to; their aliases were carried across, so a search for
-- `khoon nikalna` still resolves -- to a real NOS. One filter here covers all
-- four branches above, which is why the join is worth keeping.
WHERE s.source <> 'legacy'
ORDER BY b.score DESC, s.name_en ASC
LIMIT :limit
"""
)


@dataclass(frozen=True)
class SearchHit:
    skill: Skill
    score: float
    matched_on: str
    match_kind: str


async def count_skills(db: AsyncSession) -> int:
    return (
        await db.scalar(select(func.count()).select_from(Skill).where(Skill.source != "legacy"))
        or 0
    )


async def get_skill_by_slug(db: AsyncSession, slug: str) -> Skill | None:
    """Retired skills are *not* excluded here.

    They are hidden from search and browse, but a profile or certificate may
    still reference one, and a 404 on a row we deliberately kept rather than
    deleted would be a broken link of our own making.
    """
    return await db.scalar(select(Skill).where(Skill.slug == slug))


async def list_skills(
    db: AsyncSession,
    *,
    skill_type: str | None = None,
    nsqf_level: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Skill], int]:
    """Returns a page of skills plus the total matching the same filters."""
    # Retired rows never appear in browse or facets either -- a filter option
    # that returns only legacy rows would be a control that does nothing.
    filters: list[Any] = [Skill.source != "legacy"]
    if skill_type is not None:
        filters.append(Skill.skill_type == skill_type)
    if nsqf_level is not None:
        filters.append(Skill.nsqf_level == nsqf_level)

    total = (await db.scalar(select(func.count()).select_from(Skill).where(*filters))) or 0
    rows = await db.scalars(
        select(Skill)
        .where(*filters)
        # Most-used first. name_en is the tie-break, and without it offset
        # paging over equal counts can repeat or skip rows between pages.
        .order_by(Skill.qp_count.desc(), Skill.name_en)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


@dataclass(frozen=True)
class RequirementsBundle:
    elements: list[tuple[Any, list[Any]]]
    knowledge: list[str]
    generic_skills: list[str]


@dataclass(frozen=True)
class QualificationRef:
    """A qualification that requires this unit, and on what terms."""

    qp_code: str
    version: str
    slug: str
    name_en: str
    name_hi: str | None
    job_role_en: str | None
    nsqf_level: float | None
    requirement: str
    group_name: str | None
    sector_name_en: str | None
    sector_slug: str | None


async def qualifications_for_skill(
    db: AsyncSession, skill_id: uuid.UUID, *, limit: int = 50
) -> tuple[list[QualificationRef], int]:
    """The current qualifications containing this NOS, with its contextual level.

    A NOS carries no NSQF level of its own -- none of the 27,538 in the national
    corpus do. Its level is a property of each qualification that includes it, so
    the honest answer to "what level is this unit?" is this list, not one number.
    """
    joined = (
        select(QpSkill, QualificationPack, Sector)
        .join(QualificationPack, QpSkill.qp_id == QualificationPack.id)
        .outerjoin(Sector, QualificationPack.sector_id == Sector.id)
        .where(QpSkill.skill_id == skill_id, QualificationPack.is_current.is_(True))
    )
    total = (await db.scalar(select(func.count()).select_from(joined.subquery()))) or 0
    rows = (
        await db.execute(
            joined.order_by(
                QualificationPack.nsqf_level.desc().nullslast(),
                QualificationPack.name_en,
            ).limit(limit)
        )
    ).all()
    return (
        [
            QualificationRef(
                qp_code=qp.qp_code,
                version=qp.version,
                slug=qp.slug,
                name_en=qp.name_en,
                name_hi=qp.name_hi,
                job_role_en=qp.job_role_en,
                nsqf_level=float(qp.nsqf_level) if qp.nsqf_level is not None else None,
                requirement=link.requirement,
                group_name=link.group_name,
                sector_name_en=sector.name_en if sector is not None else None,
                sector_slug=sector.slug if sector is not None else None,
            )
            for link, qp, sector in rows
        ],
        total,
    )


async def requirements_for_skill(db: AsyncSession, skill_id: uuid.UUID) -> RequirementsBundle:
    """What a standard actually requires: criteria, knowledge, generic skills.

    Ordered by the ordinals the importer assigned, which preserve the source's
    own sequence -- the criteria of a standard read as a procedure, and shuffling
    them would lose that.
    """
    elements = (
        (
            await db.execute(
                select(PerformanceElement)
                .where(PerformanceElement.skill_id == skill_id)
                .order_by(PerformanceElement.ordinal)
            )
        )
        .scalars()
        .all()
    )

    criteria: dict[uuid.UUID, list[PerformanceCriterion]] = {}
    if elements:
        rows = (
            (
                await db.execute(
                    select(PerformanceCriterion)
                    .where(PerformanceCriterion.element_id.in_([e.id for e in elements]))
                    .order_by(PerformanceCriterion.ordinal)
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            criteria.setdefault(row.element_id, []).append(row)

    knowledge = (
        await db.scalars(
            select(KnowledgeParameter.text_en)
            .where(KnowledgeParameter.skill_id == skill_id)
            .order_by(KnowledgeParameter.ordinal)
        )
    ).all()
    generic = (
        await db.scalars(
            select(GenericCriterion.text_en)
            .where(GenericCriterion.skill_id == skill_id)
            .order_by(GenericCriterion.ordinal)
        )
    ).all()
    return RequirementsBundle(
        elements=[(e, criteria.get(e.id, [])) for e in elements],
        knowledge=list(knowledge),
        generic_skills=list(generic),
    )


async def skill_facets(
    db: AsyncSession,
) -> tuple[list[tuple[float, int]], list[tuple[str, int]], int, int]:
    """Levels and types present in the taxonomy, each with its count.

    Two grouped aggregates over one table. Cheap enough to serve directly at
    21k rows, and it keeps the client's filter options from drifting away from
    the data -- see SkillFacets for why that drift is not self-announcing.
    """
    level_rows = (
        await db.execute(
            select(Skill.nsqf_level, func.count())
            .where(Skill.nsqf_level.is_not(None), Skill.source != "legacy")
            .group_by(Skill.nsqf_level)
            .order_by(Skill.nsqf_level)
        )
    ).all()
    type_rows = (
        await db.execute(
            select(Skill.skill_type, func.count())
            .where(Skill.source != "legacy")
            .group_by(Skill.skill_type)
            .order_by(func.count().desc())
        )
    ).all()
    unlevelled = (
        await db.scalar(
            select(func.count())
            .select_from(Skill)
            .where(Skill.nsqf_level.is_(None), Skill.source != "legacy")
        )
    ) or 0
    total = sum(int(r[1]) for r in type_rows)
    return (
        [(float(r[0]), int(r[1])) for r in level_rows],
        [(str(r[0]), int(r[1])) for r in type_rows],
        unlevelled,
        total,
    )


async def search_skills(db: AsyncSession, query: str, *, limit: int = 20) -> list[SearchHit]:
    """Search canonical names, descriptions and every alias surface form."""
    cleaned = query.strip()
    if not cleaned:
        return []

    limit = min(limit, MAX_SEARCH_RESULTS)
    result = await db.execute(_SEARCH_SQL, {"raw": cleaned, "limit": limit})
    ranked = result.all()
    if not ranked:
        return []

    ids: list[uuid.UUID] = [row.skill_id for row in ranked]
    skills = {s.id: s for s in (await db.scalars(select(Skill).where(Skill.id.in_(ids))))}

    # Ordering comes from SQL; rebuild it here rather than re-sorting, so the
    # ranking rules live in exactly one place.
    return [
        SearchHit(
            skill=skills[row.skill_id],
            score=float(row.score),
            matched_on=row.matched_on,
            match_kind=row.match_kind,
        )
        for row in ranked
        if row.skill_id in skills
    ]
