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
from api.modules.skills.role_aliases import ROLE_ALIASES, alias_scores

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
           CASE WHEN lower(s.name) = q.norm THEN 4.0 ELSE 3.0 END AS score,
           s.name AS matched_on,
           CASE WHEN lower(s.name) = q.norm THEN 'exact' ELSE 'prefix' END AS match_kind
    FROM skills s, q
    WHERE lower(s.name) LIKE q.norm || '%'

    UNION ALL

    -- translated names. Until ADR-041 this was `s.name_hi` beside the canonical
    -- name; it is a row in content_translations now, and searching it here is
    -- what keeps a Devanagari query working for *any* language, not only Hindi.
    SELECT ct.entity_id,
           CASE WHEN lower(ct.text) = q.norm THEN 4.0 ELSE 3.0 END,
           ct.text,
           CASE WHEN lower(ct.text) = q.norm THEN 'exact' ELSE 'prefix' END
    FROM content_translations ct, q
    WHERE ct.entity_type = 'skill'
      AND ct.field = 'name'
      AND lower(ct.text) LIKE q.norm || '%'

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
           s.name,
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
ORDER BY b.score DESC, s.name ASC
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
        # Most-used first. name is the tie-break, and without it offset
        # paging over equal counts can repeat or skip rows between pages.
        .order_by(Skill.qp_count.desc(), Skill.name)
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
    name: str
    job_role: str | None
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
                QualificationPack.name,
            ).limit(limit)
        )
    ).all()
    return (
        [
            QualificationRef(
                qp_code=qp.qp_code,
                version=qp.version,
                slug=qp.slug,
                name=qp.name,
                job_role=qp.job_role,
                nsqf_level=float(qp.nsqf_level) if qp.nsqf_level is not None else None,
                requirement=link.requirement,
                group_name=link.group_name,
                sector_name_en=sector.name if sector is not None else None,
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
            select(KnowledgeParameter.text)
            .where(KnowledgeParameter.skill_id == skill_id)
            .order_by(KnowledgeParameter.ordinal)
        )
    ).all()
    generic = (
        await db.scalars(
            select(GenericCriterion.text)
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


# ------------------------------------------------------------------ roles
#
# Sprint 23. A candidate cannot name a National Occupational Standard -- they are
# called things like "Follow infection control policies & procedures including
# biomedical waste disposal protocols" -- but they can name their job. Every one
# of the 4,424 current qualification packs carries a `job_role`, and the pack
# names its standards. So: search roles, then offer the pack's standards.
#
# This is `matching.entry_routes_for_job` reversed. That derives a qualification
# from a job's standards; this derives standards from a person's role.

MAX_ROLE_RESULTS = 30

# Tiers mirror `_SEARCH_SQL`: exact 4, prefix 3, contains 2, and fuzzy scaled so
# it can never reach 2 -- a guess must never outrank something the candidate
# literally typed. Aliases arrive pre-scored on the same tiers.
#
# **One row per role.** The same role appears under many codes: `HSS/Q5601` has
# 28 `-SI` siblings of four standards each; `BWS/Q0102` is reissued as
# `DGT/BWS/Q0102` and `IID/BWS/Q0102`. The representative is the base code
# before a `-SI` variant, then the fewest `/` segments (the SSC's own code
# rather than a reissuer's), then the most standards, then the code itself so
# the answer is stable. `-SI` is ordered, not filtered: some roles exist only
# as variants. `variants` says how many were collapsed, so the screen can.
#
# A pack with no standards is never offered -- choosing it would offer nothing.
_ROLE_SEARCH_SQL = text(
    """
WITH q AS (
    SELECT lower(btrim(CAST(:raw AS text))) AS norm
),
aliased AS (
    SELECT t.role_key, t.score
    FROM unnest(CAST(:alias_roles AS text[]), CAST(:alias_scores AS float8[]))
         AS t(role_key, score)
),
candidates AS (
    SELECT qp.id, qp.slug, qp.qp_code, qp.job_role, qp.nsqf_level, qp.sector_id,
           lower(btrim(qp.job_role)) AS role_key,
           (SELECT count(*) FROM qp_skills s WHERE s.qp_id = qp.id) AS standards
    FROM qualification_packs qp, q
    WHERE qp.is_current
      AND (lower(qp.job_role) LIKE '%' || q.norm || '%'
           OR q.norm <% lower(qp.job_role)
           OR lower(btrim(qp.job_role)) IN (SELECT role_key FROM aliased))
),
ranked AS (
    SELECT c.*,
           count(*) OVER (PARTITION BY c.role_key) AS variants,
           row_number() OVER (
               PARTITION BY c.role_key
               ORDER BY (c.qp_code ~ '-SI[0-9]+$'),
                        length(c.qp_code) - length(replace(c.qp_code, '/', '')),
                        c.standards DESC,
                        c.qp_code
           ) AS pick
    FROM candidates c
    WHERE c.standards > 0
),
scored AS (
    SELECT r.*,
           CASE WHEN r.role_key = q.norm THEN 4.0
                WHEN r.role_key LIKE q.norm || '%' THEN 3.0
                WHEN r.role_key LIKE '%' || q.norm || '%' THEN 2.0
                ELSE 0.9 * word_similarity(q.norm, r.role_key)
           END AS literal,
           coalesce((SELECT max(a.score) FROM aliased a WHERE a.role_key = r.role_key), 0)
               AS via_alias,
           -- Whole-string, not word: breaks ties between fuzzy hits in favour of
           -- a title that is *about* the query over one that merely contains a
           -- word of it. Without it "delivery boy" ranked a BIM architecture
           -- certificate second, because its title ends in "Delivery" and it
           -- happens to carry more standards.
           similarity(q.norm, r.role_key) AS closeness
    FROM ranked r, q
    WHERE r.pick = 1
)
SELECT s.slug, s.qp_code, s.job_role, s.nsqf_level, s.standards, s.variants,
       s.role_key, s.literal, s.via_alias, sec.name AS sector_name
FROM scored s
LEFT JOIN sectors sec ON sec.id = s.sector_id
ORDER BY greatest(s.literal, s.via_alias) DESC, s.closeness DESC, s.standards DESC, s.job_role
LIMIT :limit
"""
)


@dataclass(frozen=True)
class RoleHit:
    slug: str
    qp_code: str
    job_role: str
    nsqf_level: float | None
    sector_name: str | None
    standards_count: int
    variants: int
    matched_on: str
    match_kind: str


def _literal_kind(score: float) -> str:
    if score >= 4.0:
        return "exact"
    if score >= 3.0:
        return "prefix"
    if score >= 2.0:
        return "contains"
    return "fuzzy"


async def search_roles(db: AsyncSession, query: str, *, limit: int = 20) -> list[RoleHit]:
    """Roles matching what the candidate typed, one row per role."""
    cleaned = " ".join(query.split())
    if not cleaned:
        return []
    via = alias_scores(cleaned)
    rows = (
        await db.execute(
            _ROLE_SEARCH_SQL,
            {
                "raw": cleaned,
                "alias_roles": list(via),
                "alias_scores": [score for score, _ in via.values()],
                "limit": min(limit, MAX_ROLE_RESULTS),
            },
        )
    ).all()

    hits: list[RoleHit] = []
    for row in rows:
        # Whichever reached it more strongly explains it. On a tie the literal
        # match wins: it is the candidate's own words.
        if row.via_alias > row.literal:
            kind, matched_on = "alias", via[row.role_key][1]
        else:
            kind, matched_on = _literal_kind(float(row.literal)), row.job_role
        hits.append(
            RoleHit(
                slug=row.slug,
                qp_code=row.qp_code,
                job_role=row.job_role,
                nsqf_level=float(row.nsqf_level) if row.nsqf_level is not None else None,
                sector_name=row.sector_name,
                standards_count=int(row.standards),
                variants=int(row.variants),
                matched_on=matched_on,
                match_kind=kind,
            )
        )
    return hits


@dataclass(frozen=True)
class RoleStandard:
    skill: Skill
    requirement: str
    group_name: str | None
    weightage: float | None


@dataclass(frozen=True)
class RoleStandards:
    qp: QualificationPack
    sector_name: str | None
    variants: int
    standards: list[RoleStandard]


# Compulsory first: they are the qualification. Electives after, kept in their
# groups -- flattening them would turn "choose one of these" into "all of these
# are required", which is not what the standard says.
_REQUIREMENT_ORDER = {"compulsory": 0, "elective": 1, "optional": 2}


async def standards_for_role_viewed(
    db: AsyncSession, slug: str, user_id: uuid.UUID | None
) -> RoleStandards | None:
    """`standards_for_role`, measured.

    Separate from the plain lookup because `standards_for_role` is also the way
    the role picker's own tests and any later caller read a qualification, and
    recording `role_suggested` inside it would count those as somebody being
    suggested a role. The event belongs to the act of looking, so it lives in
    the function that is only ever that act.

    Counts only: which role somebody looked at is a fact about the role. The row
    carries `user_id` and nothing else that identifies them, and it is nullable
    -- this surface is deliberately open to a signed-out visitor, because a
    sign-up wizard cannot demand an account before it can help.

    `record()` commits and there is nothing uncommitted here: this is a read.

    Imported inside the function -- `analytics` loads its routes, which load
    `marketplace.models`, which load `skills`, so a module-level import would
    make the two wait on each other at boot.
    """
    found = await standards_for_role(db, slug)
    if found is None:
        return None

    from api.modules.analytics import record

    await record(
        db,
        "role_suggested",
        user_id=user_id,
        subject_type="qualification",
        subject_id=found.qp.id,
        payload={"standards": len(found.standards), "variants": found.variants},
    )
    return found


async def standards_for_role(db: AsyncSession, slug: str) -> RoleStandards | None:
    """A qualification and the standards it is made of."""
    qp = await db.scalar(select(QualificationPack).where(QualificationPack.slug == slug))
    if qp is None:
        return None

    sector_name = (
        await db.scalar(select(Sector.name).where(Sector.id == qp.sector_id))
        if qp.sector_id is not None
        else None
    )
    variants = (
        await db.scalar(
            select(func.count())
            .select_from(QualificationPack)
            .where(
                QualificationPack.is_current.is_(True),
                func.lower(func.btrim(QualificationPack.job_role))
                == func.lower(func.btrim(qp.job_role or "")),
            )
        )
    ) or 1

    rows = (
        await db.execute(select(QpSkill, Skill).join(Skill).where(QpSkill.qp_id == qp.id))
    ).all()
    standards = [
        RoleStandard(
            skill=skill,
            requirement=link.requirement,
            group_name=link.group_name,
            weightage=float(link.weightage) if link.weightage is not None else None,
        )
        for link, skill in rows
    ]
    standards.sort(
        key=lambda s: (
            _REQUIREMENT_ORDER.get(s.requirement, 3),
            s.group_name or "",
            -(s.weightage if s.weightage is not None else -1.0),
            s.skill.name,
        )
    )
    return RoleStandards(qp=qp, sector_name=sector_name, variants=variants, standards=standards)


async def unresolved_aliases(db: AsyncSession) -> list[str]:
    """Alias targets that name no current qualification with standards.

    Such an alias matches nothing and fails silently -- which is why editing
    `role_aliases.py` is verified by running this, against the real corpus.
    """
    targets = sorted({role.lower().strip() for role in ROLE_ALIASES.values()})
    rows = await db.execute(
        text(
            """
            SELECT DISTINCT lower(btrim(qp.job_role)) AS role_key
            FROM qualification_packs qp
            WHERE qp.is_current
              AND lower(btrim(qp.job_role)) = ANY(CAST(:targets AS text[]))
              AND EXISTS (SELECT 1 FROM qp_skills s WHERE s.qp_id = qp.id)
            """
        ),
        {"targets": targets},
    )
    found = {row.role_key for row in rows}
    return [t for t in targets if t not in found]


# ---------------------------------------------------------------- context
#
# A quarter of the corpus shares its name with another standard: 1,778 names
# across 4,838 rows. Searching "General Duty Assistant" returned two cards both
# titled "Broad Functions of General Duty Assistant", and nothing on either said
# how they differed -- the NOS code was dropped, and the one fact a person can
# read, which qualification each belongs to, was never sent. These are that.


@dataclass(frozen=True)
class SkillContext:
    awarding_body: str | None
    sector: str | None
    qualification_code: str | None
    qualification_name: str | None
    qualification_slug: str | None


# The representative qualification uses role search's rule -- base code before
# a -SI variant, then the SSC's own code over a reissuer's -- so a standard and
# the role it came from never name different packs.
_CONTEXT_SQL = text(
    """
WITH pack AS (
    SELECT DISTINCT ON (qs.skill_id)
           qs.skill_id, q.qp_code, q.name, q.slug
    FROM qp_skills qs
    JOIN qualification_packs q ON q.id = qs.qp_id AND q.is_current
    WHERE qs.skill_id = ANY(CAST(:ids AS uuid[]))
    ORDER BY qs.skill_id,
             (q.qp_code ~ '-SI[0-9]+$'),
             length(q.qp_code) - length(replace(q.qp_code, '/', '')),
             q.qp_code
)
SELECT s.id, ab.name AS body, sec.name AS sector,
       pack.qp_code, pack.name AS qp_name, pack.slug AS qp_slug
FROM skills s
LEFT JOIN awarding_bodies ab ON ab.id = s.awarding_body_id
LEFT JOIN sectors sec ON sec.id = s.sector_id
LEFT JOIN pack ON pack.skill_id = s.id
WHERE s.id = ANY(CAST(:ids AS uuid[]))
"""
)


async def contexts_for(
    db: AsyncSession, skill_ids: list[uuid.UUID]
) -> dict[uuid.UUID, SkillContext]:
    """Where each standard comes from, for a page of them, in one query."""
    if not skill_ids:
        return {}
    rows = await db.execute(_CONTEXT_SQL, {"ids": [str(i) for i in skill_ids]})
    return {
        row.id: SkillContext(
            awarding_body=row.body,
            sector=row.sector,
            qualification_code=row.qp_code,
            qualification_name=row.qp_name,
            qualification_slug=row.qp_slug,
        )
        for row in rows
    }
