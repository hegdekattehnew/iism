"""What the two publishing surfaces genuinely share.

`publishing.py` and `course_publishing.py` are deliberately siblings rather than
one generalisation: a job's requirements carry importance and a mandatory flag
because a match is scored against them, a course's carry only the level taught,
and duplicates therefore collapse on opposite rules. Those differences are real
and must stay apart.

What must **not** stay apart is the part ADR-026 calls out by name — *"the same
service layer and validation rules"*. Three things were byte-identical in both
modules, and validation duplicated is validation that eventually differs:

* which standards exist, and the refusal of ones that do not;
* the refusal of retired `legacy` rows;
* re-reading a listing with its relationships populated.

The retired-standard rule had **no test in either copy**, which is exactly how a
duplicated rule rots: nothing fails when one side drifts.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.text import slugify
from api.modules.skills.models import Skill


async def resolve_standards(
    db: AsyncSession, slugs: list[str], *, verb: str
) -> dict[str, uuid.UUID]:
    """Slugs to skill ids, refusing anything unknown or retired.

    `verb` is "required" or "taught" — the only thing that differs between the
    two callers, and only in the message a person reads.

    Retired rows are refused rather than silently accepted: Sprint 9 made the
    national taxonomy the operational vocabulary, and a listing anchored to a
    `legacy` row would score against nothing at all. Matching compares at
    concept level and `legacy` rows are excluded from it, so the listing would
    be published and permanently unmatchable.
    """
    if not slugs:
        return {}

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
    retired = sorted({s for s in slugs if found[s][1] == "legacy"})
    if retired:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Retired standards cannot be {verb}: {', '.join(retired)}",
        )
    return {slug: found[slug][0] for slug in found}


async def unique_slug(db: AsyncSession, column: Any, *parts: str | None) -> str:
    """A readable slug, disambiguated only when it must be.

    A job takes title and district, a course title alone — hence `*parts`. A
    Hindi-only title transliterates to nothing, so there is a fallback rather
    than an empty slug.
    """
    pieces = [slugify(p)[:70].strip("-") for p in parts if p]
    base = "-".join(p for p in pieces if p) or "listing"
    taken = set((await db.scalars(select(column).where(column.like(f"{base}%")))).all())
    if base not in taken:
        return base
    for n in range(2, 200):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    return f"{base}-{datetime.now(UTC).timestamp():.0f}"


async def load_with_skills(
    db: AsyncSession, model: Any, link: Any, listing_id: uuid.UUID, *, label: str
) -> Any:
    """Re-read a listing with its standards and tenant populated.

    `populate_existing` because the instance is already in the session's
    identity map with a stale collection after the delete-and-rewrite that
    precedes every call — without it the query succeeds and quietly returns the
    previous set of standards.
    """
    listing = await db.scalar(
        select(model)
        .where(model.id == listing_id)
        .options(
            selectinload(model.skills).selectinload(link.skill),
            selectinload(model.tenant),
        )
        .execution_options(populate_existing=True)
    )
    if listing is None:  # pragma: no cover - just written
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")
    return listing
