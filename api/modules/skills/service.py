"""Business logic for the skills module.

Routes validate and delegate here; they contain no logic themselves (CLAUDE.md).
"""

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.embeddings import get_embedding_provider
from api.core.text import WORD_SYNONYMS, expand_query_terms
from api.modules.skills.content import (
    GenericCriterion,
    KnowledgeParameter,
    PerformanceCriterion,
    PerformanceElement,
)
from api.modules.skills.hierarchy import QpSkill, QualificationPack, Sector
from api.modules.skills.models import Skill
from api.modules.skills.role_aliases import MIN_ALIAS_PREFIX, ROLE_ALIASES

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


async def get_skill_by_nos_code(db: AsyncSession, nos_code: str) -> Skill | None:
    """`nos_code` is unique in the corpus (unlike names or sector-local ids,
    see CLAUDE.md), which is what makes it the right key for an external
    system to cite a standard by (Sprint 35, BL-3.1) -- a slug is this
    platform's own identifier and no assessment provider will have one."""
    return await db.scalar(select(Skill).where(Skill.nos_code == nos_code))


async def embedding_text_for_skills(db: AsyncSession, skill_ids: list[uuid.UUID]) -> str:
    """The text a semantic-similarity embedding is computed from (Sprint 36,
    BL-5.1): performance criteria, never a skill's own title. "OJT" and
    "Project" are real unit titles in this corpus and embed to noise on their
    own -- the assessable content underneath a title is what actually
    describes the standard. Falls back to a skill's own `description`, then
    its `name`, only for the ~35% of standards with no recorded performance
    criteria at all.
    """
    if not skill_ids:
        return ""
    criteria_rows = (
        await db.execute(
            select(PerformanceElement.skill_id, PerformanceCriterion.description)
            .join(PerformanceCriterion, PerformanceCriterion.element_id == PerformanceElement.id)
            .where(PerformanceElement.skill_id.in_(skill_ids))
        )
    ).all()
    by_skill: dict[uuid.UUID, list[str]] = {}
    for skill_id, description in criteria_rows:
        by_skill.setdefault(skill_id, []).append(description)

    missing = [sid for sid in skill_ids if sid not in by_skill]
    fallback_rows = (
        (
            await db.execute(
                select(Skill.id, Skill.name, Skill.description).where(Skill.id.in_(missing))
            )
        ).all()
        if missing
        else []
    )
    fallback_text = {row.id: row.description or row.name for row in fallback_rows}

    parts = [text for sid in skill_ids for text in by_skill.get(sid, [])]
    parts.extend(fallback_text.get(sid, "") for sid in missing)
    return " ".join(p for p in parts if p)


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

# Cosine similarity floor for the semantic tier below (Sprint 40, foundation).
# **A starting constant, not a validated one** -- real measurement against the
# real model this session found genuinely unreliable separation at this task:
# a true pair ("it support" / "Certificate in Computer Hardware & Networking")
# scored 0.16, *below* a false one ("cashier" / "AC Technician") at 0.33. This
# value catches the clearer true positives measured (0.32-0.81) while
# excluding the clearest noise-floor negatives (below ~0.2); it does not catch
# every true positive, and a follow-up tuning pass against a real sample --
# not five hand-picked pairs -- is still owed before trusting this threshold.
SEMANTIC_MIN_SIMILARITY = 0.30

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
# **The one rule for which pack stands for a role** (Sprint 42). Role search and
# the career ladder both collapse a role's many codes to one, and a second copy of
# this ordering is how the two would one day name different packs for the same job
# title. It is a SQL fragment because both callers pick inside a query; `c` is the
# candidate row and must carry `qp_code` and `standards` (the pack's standard count).
#
# **A general pack stands for a role before a disability-track one** (Sprint 43,
# ADR-050): every disability-track pack carries a `PWD/` code (69 roles, no
# exception), and twelve roles have both kinds. The old order preferred the general
# pack only because it usually has fewer `/` segments -- a coincidence, not a rule.
ROLE_REPRESENTATIVE_ORDER = """(c.qp_code LIKE 'PWD/%'),
                        (c.qp_code ~ '-SI[0-9]+$'),
                        length(c.qp_code) - length(replace(c.qp_code, '/', '')),
                        c.standards DESC,
                        c.qp_code"""

_ROLE_SEARCH_SQL = text(
    """
WITH q AS (
    SELECT lower(btrim(CAST(:raw AS text))) AS norm
),
aliased AS (
    -- `role_aliases` (Sprint 23, moved from a Python dict this session): a
    -- whole alias scores like an exact match (4), a half-typed one like a
    -- prefix (3) -- the same tiers the literal match below uses, so a guess
    -- via an alias never outranks something the candidate actually typed.
    SELECT ra.surface_form,
           lower(btrim(ra.job_role)) AS role_key,
           CASE WHEN ra.surface_form = q.norm THEN 4.0 ELSE 3.0 END AS score
    FROM role_aliases ra, q
    WHERE ra.surface_form = q.norm
       OR (length(q.norm) >= :min_alias_prefix AND ra.surface_form LIKE q.norm || '%')
),
candidates AS (
    SELECT qp.id, qp.slug, qp.qp_code, qp.job_role, qp.nsqf_level, qp.sector_id,
           lower(btrim(qp.job_role)) AS role_key,
           (SELECT count(*) FROM qp_skills s WHERE s.qp_id = qp.id) AS standards
    FROM qualification_packs qp, q
    WHERE qp.is_current
      AND (lower(qp.job_role) LIKE '%' || q.norm || '%'
           OR q.norm <% lower(qp.job_role)
           OR lower(btrim(qp.job_role)) IN (SELECT role_key FROM aliased)
           -- Sprint 43: every word of a multi-word query, in any order. "hotel
           -- waiter" and "bank clerk" matched nothing, because matching was a
           -- whole-string substring or a trigram. `:terms` is empty for a
           -- one-word query, so this is false there.
           OR (cardinality(CAST(:terms AS text[])) >= 2 AND NOT EXISTS (
               SELECT 1 FROM unnest(CAST(:terms AS text[])) AS w(word)
               WHERE lower(qp.job_role) NOT LIKE '%' || w.word || '%'
           ))
           -- Generic word-level synonyms ("tech" -> "technology"), never
           -- role-specific -- affects only which rows are eligible to
           -- appear, never `scored`'s ranking below, which stays keyed on
           -- what the candidate actually typed.
           OR EXISTS (
               SELECT 1 FROM unnest(CAST(:synonym_terms AS text[])) AS t(term)
               WHERE lower(qp.job_role) LIKE '%' || t.term || '%'
           )
           -- Sprint 45: every word of a multi-word query, each met by itself or by
           -- a synonym ("mfg operator" -> a title with "manufacturing" and
           -- "operator" in it, in any order). `:term_groups` is `[]` unless some
           -- word has a synonym, so this is false for every other query.
           OR (jsonb_array_length(CAST(:term_groups AS jsonb)) > 0 AND NOT EXISTS (
               SELECT 1 FROM jsonb_array_elements(CAST(:term_groups AS jsonb)) AS g(alts)
               WHERE NOT EXISTS (
                   SELECT 1 FROM jsonb_array_elements_text(g.alts) AS a(alt)
                   WHERE lower(qp.job_role) LIKE '%' || a.alt || '%'
               )
           ))
           -- Semantic tier (Sprint 40, foundation): only ever reached when a
           -- real embedding provider is active (`:query_embedding` is NULL
           -- under the hashing placeholder, so this branch is always false
           -- there -- token-overlap "similarity" would add noise, not
           -- signal). Admits a row into the pool; it does not touch `scored`'s
           -- ranking below, so a semantic-only match still lands on the fuzzy
           -- tier there, never above a literal or aliased one.
           OR (
               CAST(:query_embedding AS vector) IS NOT NULL
               AND qp.embedding IS NOT NULL
               AND 1 - (qp.embedding <=> CAST(:query_embedding AS vector))
                   >= :semantic_min_similarity
           ))
),
ranked AS (
    SELECT c.*,
           count(*) OVER (PARTITION BY c.role_key) AS variants,
           row_number() OVER (
               PARTITION BY c.role_key
               ORDER BY __REPRESENTATIVE_ORDER__
           ) AS pick
    FROM candidates c
    WHERE c.standards > 0
),
scored AS (
    SELECT r.*,
           CASE WHEN r.role_key = q.norm THEN 4.0
                WHEN r.role_key LIKE q.norm || '%' THEN 3.0
                WHEN r.role_key LIKE '%' || q.norm || '%' THEN 2.0
                -- All the words, in any order: above the fuzzy ceiling (0.9) and
                -- below a whole-string "contains", so a guess never outranks
                -- something the person literally typed.
                WHEN cardinality(CAST(:terms AS text[])) >= 2 AND NOT EXISTS (
                    SELECT 1 FROM unnest(CAST(:terms AS text[])) AS w(word)
                    WHERE r.role_key NOT LIKE '%' || w.word || '%'
                ) THEN 1.5
                -- Sprint 45: the query with an abbreviation spelled out ("mfg
                -- technician" -> "manufacturing technician") found whole in the
                -- title. Below *every* literal tier, including all-the-words-in-any-
                -- order: what the person typed outranks what we expanded it to. It
                -- used to be admitted and then scored as a fuzzy guess, below titles
                -- that merely resembled the query.
                WHEN EXISTS (
                    SELECT 1 FROM unnest(CAST(:synonym_terms AS text[])) AS t(term)
                    WHERE r.role_key LIKE '%' || t.term || '%'
                ) THEN 1.4
                -- All the words in any order, any of them met by a synonym: under the
                -- expanded phrase, as a looser form of the same thing.
                WHEN jsonb_array_length(CAST(:term_groups AS jsonb)) > 0 AND NOT EXISTS (
                    SELECT 1 FROM jsonb_array_elements(CAST(:term_groups AS jsonb)) AS g(alts)
                    WHERE NOT EXISTS (
                        SELECT 1 FROM jsonb_array_elements_text(g.alts) AS a(alt)
                        WHERE r.role_key LIKE '%' || a.alt || '%'
                    )
                ) THEN 1.3
                ELSE 0.9 * word_similarity(q.norm, r.role_key)
           END AS literal,
           -- Sprint 43: a disability-track pack is demoted by one match tier (the
           -- ORDER BY below subtracts 1.01) unless the query asked for one, or is
           -- exactly its title (`literal` 4.0): somebody who typed "Pressman" in
           -- full is not helped by being shown something else first. One tier, not
           -- last place: where it is the only literal match, "hr executive" should
           -- still reach it ahead of "Executive Housekeeper". It loses to an equally
           -- good general pack, which is the case the demotion exists for.
           -- `PWD/` is the code every one of them carries.
           (r.qp_code LIKE 'PWD/%') AS disability_track,
           coalesce((SELECT max(a.score) FROM aliased a WHERE a.role_key = r.role_key), 0)
               AS via_alias,
           -- The alias that produced that max score, so the caller can name
           -- it without a second lookup -- ties broken alphabetically, same
           -- as everything else here, so the answer is stable.
           (
               SELECT a.surface_form FROM aliased a WHERE a.role_key = r.role_key
               ORDER BY a.score DESC, a.surface_form
               LIMIT 1
           ) AS via_alias_surface_form,
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
       s.role_key, s.literal, s.via_alias, s.via_alias_surface_form, sec.name AS sector_name
FROM scored s
LEFT JOIN sectors sec ON sec.id = s.sector_id
ORDER BY greatest(s.literal, s.via_alias)
             - CASE WHEN s.disability_track AND s.literal < 4.0
                         AND NOT CAST(:asks_disability AS boolean)
                    THEN 1.01 ELSE 0 END DESC,
         -- Sprint 43: on a tie, the role a curated alias vouches for beats one that
         -- merely starts with the same letters. A half-typed alias and a literal
         -- prefix both score 3.0, and `closeness` below always favoured the
         -- literal one, so "war" listed Warper above General Duty Assistant.
         (s.via_alias > 0) DESC,
         s.closeness DESC, s.standards DESC, s.job_role
LIMIT :limit
""".replace("__REPRESENTATIVE_ORDER__", ROLE_REPRESENTATIVE_ORDER)
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


def _pgvector_literal(vector: list[float]) -> str:
    """`[0.1,0.2,...]`, pgvector's own text form -- the portable way to bind a
    vector into a raw `text()` query, since `CAST(:param AS vector)` accepts
    this from any driver without a type adapter registered for the parameter."""
    return "[" + ",".join(repr(v) for v in vector) + "]"


# Words that do not narrow a role: "assistant of the ward" and "assistant ward" are
# the same ask. Kept to the few that carry no meaning in any sector.
_QUERY_STOPWORDS = frozenset({"and", "of", "the", "in", "for", "a", "an", "to"})

# A query that is itself about disability-track work. Only then does a
# disability-track pack compete on equal terms.
_ASKS_DISABILITY = ("divyang", "pwd", "disab")


def _query_terms(cleaned: str) -> list[str]:
    """The words an all-words match must find, or `[]` for a one-word query.

    `%`, `_` and `\\` are stripped because the terms are spliced into `LIKE`
    patterns, where they would be wildcards the person never meant. Nothing else
    is stripped: splitting on punctuation would cut a Devanagari word at its
    vowel signs, which Python does not count as alphanumeric.
    """
    seen: list[str] = []
    for word in cleaned.lower().split():
        word = "".join(ch for ch in word if ch not in "%_\\")
        if word and word not in _QUERY_STOPWORDS and word not in seen:
            seen.append(word)
    return seen if len(seen) >= 2 else []


def _term_groups(cleaned: str) -> list[list[str]]:
    """Each word of a multi-word query with what it may stand for, or `[]`.

    `"mfg operator"` becomes `[["mfg", "manufacturing"], ["operator"]]`: a title
    meets the query if it carries, for every group, any one of its words (Sprint
    45, BL-12.14). Without this the synonym only applied to the **whole** query
    string, so `mfg operator` found no `Manufacturing ... Operator` unless that
    exact phrase was in the title, and returned every operator in the corpus.

    Empty when no word has a synonym -- the literal all-words rule already covers
    that, and a second rule that repeats it would only add a way to disagree with
    it. Whole words only (the reason `WORD_SYNONYMS` is matched that way), and a
    word carrying a `LIKE` wildcard is looked up as itself, never as what its
    stripped form happens to spell.
    """
    groups: list[list[str]] = []
    seen: set[str] = set()
    for raw in cleaned.lower().split():
        word = "".join(ch for ch in raw if ch not in "%_\\")
        if not word or word in _QUERY_STOPWORDS or word in seen:
            continue
        seen.add(word)
        groups.append([word, *WORD_SYNONYMS.get(raw, [])] if word == raw else [word])
    if len(groups) < 2 or all(len(g) == 1 for g in groups):
        return []
    return groups


def _literal_kind(score: float) -> str:
    if score >= 4.0:
        return "exact"
    if score >= 3.0:
        return "prefix"
    if score >= 2.0:
        return "contains"
    if score >= 1.0:
        return "words"
    return "fuzzy"


async def search_roles(db: AsyncSession, query: str, *, limit: int = 20) -> list[RoleHit]:
    """Roles matching what the candidate typed, one row per role."""
    cleaned = " ".join(query.split())
    if not cleaned:
        return []
    # Generic word-synonym expansions only ("tech" -> "technology") -- the
    # original is excluded, since `_ROLE_SEARCH_SQL`'s own `q.norm`-based
    # conditions already cover it.
    synonym_terms = expand_query_terms(cleaned)[1:]
    # Embedding the query live is only worth the cost -- and only means
    # anything -- when a real provider is behind the port. Under the hashing
    # placeholder this stays `None`, and the SQL's own `IS NOT NULL` guard
    # turns the whole semantic branch off, exactly as it does with no
    # embedding column populated at all.
    provider = get_embedding_provider()
    query_embedding = (
        _pgvector_literal(provider.embed(cleaned)) if provider.name != "hashing" else None
    )
    rows = (
        await db.execute(
            _ROLE_SEARCH_SQL,
            {
                "raw": cleaned,
                "min_alias_prefix": MIN_ALIAS_PREFIX,
                "synonym_terms": synonym_terms,
                "query_embedding": query_embedding,
                "semantic_min_similarity": SEMANTIC_MIN_SIMILARITY,
                "terms": _query_terms(cleaned),
                "term_groups": json.dumps(_term_groups(cleaned)),
                "asks_disability": any(t in cleaned.lower() for t in _ASKS_DISABILITY),
                "limit": min(limit, MAX_ROLE_RESULTS),
            },
        )
    ).all()

    hits: list[RoleHit] = []
    for row in rows:
        # Whichever reached it more strongly explains it. On a tie the literal
        # match wins: it is the candidate's own words.
        if row.via_alias > row.literal:
            kind, matched_on = "alias", row.via_alias_surface_form
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


@dataclass(frozen=True)
class AliasReport:
    """What is wrong, and what is merely ambiguous, in a set of role aliases."""

    unresolved: list[str]
    """Targets that name no current qualification with standards. Such an alias
    matches nothing, silently."""
    disability_track: list[tuple[str, str, str]]
    """`(key, target, qp_code)`: the pack that would stand for the target is a
    disability-track one (a `PWD/` code). The rule has always been "point at the
    general pack"; this is the first check that could see a breach."""
    shadowed: list[tuple[str, str]]
    """`(key, literal role)`: the key *is* a role's exact title but is aliased
    to a different role, so a typed title would send somebody elsewhere."""
    prefix_collisions: dict[str, list[str]]
    """Every prefix of at least `MIN_ALIAS_PREFIX` characters that two or more
    different targets claim. Reported, never a failure: a typeahead is allowed to
    be ambiguous, it just has to be known."""

    @property
    def failures(self) -> bool:
        return bool(self.unresolved or self.disability_track or self.shadowed)


def alias_prefix_collisions(aliases: Mapping[str, str]) -> dict[str, list[str]]:
    """Prefixes claimed by more than one target. Pure, so it is tested without a corpus."""
    claimed: dict[str, set[str]] = {}
    for key, target in aliases.items():
        for n in range(MIN_ALIAS_PREFIX, len(key) + 1):
            claimed.setdefault(key[:n], set()).add(target)
    return {p: sorted(t) for p, t in sorted(claimed.items()) if len(t) > 1}


async def alias_problems(db: AsyncSession, aliases: Mapping[str, str] | None = None) -> AliasReport:
    """Check role aliases against the corpus (Sprint 43, ADR-050).

    Defaults to the authored `ROLE_ALIASES`; the tests pass their own. Editing
    `role_aliases.py` is verified by running this against the real corpus
    (`make check-role-aliases`), which is why it cannot run in CI.
    """
    aliases = ROLE_ALIASES if aliases is None else aliases
    targets = sorted({role.lower().strip() for role in aliases.values()})
    keys = sorted({key.lower().strip() for key in aliases})
    # The same representative pick role search makes, by the same rule: this is
    # what an alias actually resolves to.
    rows = (
        await db.execute(
            text(
                f"""
                WITH c AS (
                    SELECT qp.qp_code, lower(btrim(qp.job_role)) AS role_key,
                           (SELECT count(*) FROM qp_skills s WHERE s.qp_id = qp.id) AS standards
                    FROM qualification_packs qp
                    WHERE qp.is_current AND qp.job_role IS NOT NULL
                )
                SELECT DISTINCT ON (c.role_key) c.role_key, c.qp_code
                FROM c
                WHERE c.standards > 0
                  AND (c.role_key = ANY(CAST(:targets AS text[]))
                       OR c.role_key = ANY(CAST(:keys AS text[])))
                ORDER BY c.role_key, {ROLE_REPRESENTATIVE_ORDER}
                """
            ),
            {"targets": targets, "keys": keys},
        )
    ).all()
    representative = {row.role_key: row.qp_code for row in rows}

    unresolved = [t for t in targets if t not in representative]
    disability_track = sorted(
        (key, target, representative[target.lower().strip()])
        for key, target in aliases.items()
        if representative.get(target.lower().strip(), "").startswith("PWD/")
    )
    shadowed = sorted(
        (key, key.lower().strip())
        for key, target in aliases.items()
        if key.lower().strip() in representative and key.lower().strip() != target.lower().strip()
    )
    return AliasReport(
        unresolved=unresolved,
        disability_track=disability_track,
        shadowed=shadowed,
        prefix_collisions=alias_prefix_collisions(
            {k.lower().strip(): v for k, v in aliases.items()}
        ),
    )


async def unresolved_aliases(db: AsyncSession) -> list[str]:
    """Alias targets that name no current qualification with standards.

    Kept for the callers that only want this one answer; `alias_problems` is the
    full check.
    """
    return (await alias_problems(db)).unresolved


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


# ----------------------------------------------------------- the career ladder
#
# (Sprint 42, ADR-049.) "Which roles build on this one" is a **taxonomy fact**, so
# it is answered here, from the qualification data, and not by whoever asks.
#
# Nothing in the national data says "role A leads to role B": entry routes name a
# *minimum prior level* in 1,882 packs and a specific pack in five, and
# `SkillRelation` has no edges. So a step is *derived*, and each one carries the
# evidence it was derived from, so a reader can judge it:
#
#   * a higher NSQF level, by at most `LADDER_MAX_RISE` -- a rung, not a leap;
#   * at least one **specific** compulsory standard in common with the starting
#     role, compared at concept level (the key `courses_closing_gap` uses). A
#     standard that turns up in compulsory lists across `GENERIC_STANDARD_SECTORS`
#     or more sectors ("Employability Skills", "Communication Skills") is not
#     evidence of anything: left in, a General Duty Assistant "led to" an
#     Automotive technician through one shared employability unit;
#   * compulsory standards of its own -- an elective-only pack has nothing to
#     score a person against.
#
# Same occupation and a shared NCO code are **corroboration, not grounds**: they
# are returned and shown, and break ties, but a step with neither a specific
# shared standard nor anything else is not offered. Occupation alone put a
# Beauty Therapist after a Retail Sales Associate, because one disability-track
# "occupation" is a catch-all. Divyangjan-track packs are left out unless the
# starting role is itself one -- the same job twice is not a next step.
#
# One row per role, picked by `ROLE_REPRESENTATIVE_ORDER`: the same rule role
# search uses, so the two cannot name different packs for one job title.
LADDER_MAX_RISE = 2.0
MAX_LADDER_STEPS = 8
GENERIC_STANDARD_SECTORS = 3

_LADDER_SQL = text(
    """
WITH f AS (
    SELECT id, nsqf_level, occupation_id,
           (job_role ILIKE '%divyangjan%') AS is_divyangjan
    FROM qualification_packs
    WHERE slug = :slug AND is_current AND nsqf_level IS NOT NULL
),
generic AS MATERIALIZED (
    SELECT coalesce(k.concept_id, k.id) AS key
    FROM qp_skills s
    JOIN skills k ON k.id = s.skill_id
    JOIN qualification_packs p ON p.id = s.qp_id
    WHERE p.is_current AND s.requirement = 'compulsory'
    GROUP BY 1
    HAVING count(DISTINCT p.sector_id) >= :generic_sectors
),
f_keys AS MATERIALIZED (
    SELECT DISTINCT coalesce(k.concept_id, k.id) AS key
    FROM qp_skills s
    JOIN skills k ON k.id = s.skill_id
    JOIN f ON s.qp_id = f.id
    WHERE s.requirement = 'compulsory'
      AND coalesce(k.concept_id, k.id) NOT IN (SELECT key FROM generic)
),
f_nco AS (
    SELECT n.nco_code FROM qp_nco_codes n JOIN f ON n.qp_id = f.id
),
windowed AS (
    SELECT qp.id, qp.slug, qp.qp_code, qp.job_role, qp.nsqf_level, qp.sector_id,
           qp.occupation_id, lower(btrim(qp.job_role)) AS role_key,
           coalesce(qp.occupation_id = f.occupation_id, false) AS same_occupation
    FROM qualification_packs qp, f
    WHERE qp.is_current
      AND qp.id <> f.id
      AND qp.job_role IS NOT NULL
      AND (f.is_divyangjan OR qp.job_role NOT ILIKE '%divyangjan%')
      AND qp.nsqf_level > f.nsqf_level
      AND qp.nsqf_level <= f.nsqf_level + CAST(:max_rise AS numeric)
),
candidates AS (
    SELECT w.*,
           (SELECT count(*) FROM qp_skills s WHERE s.qp_id = w.id) AS standards,
           (SELECT count(*) FROM qp_skills s
             WHERE s.qp_id = w.id AND s.requirement = 'compulsory') AS compulsory,
           (SELECT count(*) FROM qp_skills s JOIN skills k ON k.id = s.skill_id
             WHERE s.qp_id = w.id AND s.requirement = 'compulsory'
               AND coalesce(k.concept_id, k.id) IN (SELECT key FROM f_keys)) AS shared,
           EXISTS (SELECT 1 FROM qp_nco_codes n
                    WHERE n.qp_id = w.id AND n.nco_code IN (SELECT nco_code FROM f_nco))
               AS shared_nco
    FROM windowed w
),
related AS (
    SELECT c.* FROM candidates c
    WHERE c.compulsory > 0 AND c.shared > 0
),
ranked AS (
    SELECT c.*,
           count(*) OVER (PARTITION BY c.role_key) AS variants,
           row_number() OVER (
               PARTITION BY c.role_key
               ORDER BY __REPRESENTATIVE_ORDER__
           ) AS pick
    FROM related c
)
SELECT r.id, r.slug, r.qp_code, r.job_role, r.nsqf_level, r.standards, r.compulsory,
       r.shared, r.same_occupation, r.shared_nco, r.variants, sec.name AS sector_name
FROM ranked r
LEFT JOIN sectors sec ON sec.id = r.sector_id
WHERE r.pick = 1
-- How much of the role is already shared, then corroboration, then the nearest
-- rung, then a stable tail.
ORDER BY (r.shared::float / r.compulsory) DESC,
         (r.same_occupation OR r.shared_nco) DESC,
         r.nsqf_level, r.job_role
LIMIT :limit
""".replace("__REPRESENTATIVE_ORDER__", ROLE_REPRESENTATIVE_ORDER)
)


@dataclass(frozen=True)
class RoleRef:
    """A qualification pack seen as a role: where a ladder starts."""

    qp_id: uuid.UUID
    slug: str
    qp_code: str
    job_role: str
    nsqf_level: float
    sector_name: str | None


@dataclass(frozen=True)
class RoleStepUp:
    """A role that builds on the starting one, and the evidence it does."""

    qp_id: uuid.UUID
    slug: str
    qp_code: str
    job_role: str
    nsqf_level: float
    sector_name: str | None
    standards_count: int
    compulsory_count: int
    shared_standards: int
    """Specific (non-generic) compulsory standards this role shares with the
    starting role. Always at least one: it is what makes a step a step."""
    same_occupation: bool
    shared_nco: bool
    variants: int


@dataclass(frozen=True)
class RoleLadder:
    anchor: RoleRef
    steps: list[RoleStepUp]


async def roles_above(
    db: AsyncSession,
    slug: str,
    *,
    max_rise: float = LADDER_MAX_RISE,
    limit: int = MAX_LADDER_STEPS,
) -> RoleLadder | None:
    """The roles that build on one, most-shared first.

    `None` is an unknown (or retired, or level-less) starting role, which is a
    different answer from an empty list: "our data shows no further step from
    this role" is something the page can say, "that role does not exist" is not.
    """
    anchor = (
        await db.execute(
            select(QualificationPack, Sector.name)
            .outerjoin(Sector, Sector.id == QualificationPack.sector_id)
            .where(
                QualificationPack.slug == slug,
                QualificationPack.is_current.is_(True),
                QualificationPack.nsqf_level.is_not(None),
            )
        )
    ).first()
    if anchor is None:
        return None
    qp, sector_name = anchor

    rows = (
        await db.execute(
            _LADDER_SQL,
            {
                "slug": slug,
                "max_rise": max_rise,
                "generic_sectors": GENERIC_STANDARD_SECTORS,
                "limit": min(limit, MAX_LADDER_STEPS),
            },
        )
    ).all()
    return RoleLadder(
        anchor=RoleRef(
            qp_id=qp.id,
            slug=qp.slug,
            qp_code=qp.qp_code,
            job_role=qp.job_role or qp.name,
            nsqf_level=float(qp.nsqf_level),
            sector_name=sector_name,
        ),
        steps=[
            RoleStepUp(
                qp_id=r.id,
                slug=r.slug,
                qp_code=r.qp_code,
                job_role=r.job_role,
                nsqf_level=float(r.nsqf_level),
                sector_name=r.sector_name,
                standards_count=r.standards,
                compulsory_count=r.compulsory,
                shared_standards=r.shared,
                same_occupation=bool(r.same_occupation),
                shared_nco=bool(r.shared_nco),
                variants=r.variants,
            )
            for r in rows
        ],
    )
