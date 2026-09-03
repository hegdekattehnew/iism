"""Business logic for the skills module.

Routes validate and delegate here; they contain no logic themselves (CLAUDE.md).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

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
    return await db.scalar(select(func.count()).select_from(Skill)) or 0


async def get_skill_by_slug(db: AsyncSession, slug: str) -> Skill | None:
    return await db.scalar(select(Skill).where(Skill.slug == slug))


async def list_skills(
    db: AsyncSession,
    *,
    skill_type: str | None = None,
    nsqf_level: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Skill], int]:
    """Returns a page of skills plus the total matching the same filters."""
    filters = []
    if skill_type is not None:
        filters.append(Skill.skill_type == skill_type)
    if nsqf_level is not None:
        filters.append(Skill.nsqf_level == nsqf_level)

    total = (await db.scalar(select(func.count()).select_from(Skill).where(*filters))) or 0
    rows = await db.scalars(
        select(Skill).where(*filters).order_by(Skill.name_en).limit(limit).offset(offset)
    )
    return list(rows), total


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
