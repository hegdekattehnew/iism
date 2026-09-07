"""Employers writing their own listings.

Until now every job in the database was put there by
`scripts/seed_marketplace.py`, and `marketplace/service.py` imported only
`select`. That script is the specification this module implements: what a
listing must carry, and how its required standards are written.

Three rules it inherits from the seed, each of which prevented a real failure
there and would cause the same one here:

* **`JobSkill` is written by full replacement, not diff.** A partial update that
  leaves a stale link behind is a requirement nobody typed.
* **Duplicate links merge on the strongest signal** — highest importance,
  mandatory beating optional. `uq_job_skill` makes a duplicate a constraint
  violation rather than two requirements, and understating either would weaken
  a requirement the employer actually stated.
* **A job with no required standards is invisible to matching.** The seed fails
  loudly on that; publishing refuses.

And one the seed never had to think about, because it ran alongside the
importer: **geography resolves on write.** `state_id` is what
`match_jobs(state_id=…)` filters on, so a listing without it is findable at
`/jobs` and unfindable by anyone matching on location.
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.text import slugify
from api.modules.geography import resolve_location
from api.modules.marketplace.models import Job, JobSkill
from api.modules.marketplace.schemas import JobIn, JobSkillIn
from api.modules.skills.models import Skill

# Fields copied straight from the payload. Listed rather than `model_dump()`ed
# wholesale so `search_vector` -- GENERATED ALWAYS, and rejected by Postgres on
# any write -- can never reach an INSERT by way of a schema someone extended.
_PLAIN_FIELDS = (
    "title_en",
    "title_hi",
    "description_en",
    "description_hi",
    "location_state",
    "location_district",
    "employment_type",
    "experience_min_years",
    "experience_max_years",
    "salary_min_inr",
    "salary_max_inr",
    "nsqf_level_min",
)


async def _unique_slug(db: AsyncSession, title: str, district: str | None) -> str:
    """`general-duty-assistant-chennai`, disambiguated only when it must be.

    Title and district, because that is what a person searching recognises, and
    what the seeded slugs already look like. A Hindi-only title slugifies to
    nothing, so there is a fallback.
    """
    parts = [slugify(title)[:70].strip("-"), slugify(district or "").strip("-")]
    base = "-".join(p for p in parts if p) or "vacancy"
    taken = set((await db.scalars(select(Job.slug).where(Job.slug.like(f"{base}%")))).all())
    if base not in taken:
        return base
    for n in range(2, 200):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    return f"{base}-{datetime.now(UTC).timestamp():.0f}"


async def _resolve_skills(
    db: AsyncSession, rows: list[JobSkillIn]
) -> list[tuple[uuid.UUID, int, bool]]:
    """Slugs to skill ids, merged on the strongest signal.

    A retired `legacy` skill is refused rather than silently accepted: the whole
    point of Sprint 9 was that the national taxonomy is the operational
    vocabulary, and a job anchored to a retired row would score against nothing.
    """
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
    retired = sorted(s for s in slugs if found[s][1] == "legacy")
    if retired:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Retired standards cannot be required: {', '.join(retired)}",
        )

    merged: dict[uuid.UUID, tuple[int, bool]] = {}
    for row in rows:
        skill_id = found[row.skill_slug][0]
        importance, mandatory = merged.get(skill_id, (0, False))
        merged[skill_id] = (
            max(importance, row.importance),
            mandatory or row.is_mandatory,
        )
    return [(sid, imp, mand) for sid, (imp, mand) in merged.items()]


async def _write_skills(db: AsyncSession, job: Job, rows: list[JobSkillIn]) -> None:
    resolved = await _resolve_skills(db, rows)
    await db.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
    for skill_id, importance, is_mandatory in resolved:
        db.add(
            JobSkill(
                job_id=job.id,
                skill_id=skill_id,
                importance=importance,
                is_mandatory=is_mandatory,
            )
        )
    await db.flush()


async def _load(db: AsyncSession, job_id: uuid.UUID) -> Job:
    """Re-read with relationships populated.

    `populate_existing` because the instance is already in the identity map with
    a stale `skills` collection after the delete-and-rewrite above -- without it
    the query succeeds and quietly returns the previous requirements.
    """
    job = await db.scalar(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.skills).selectinload(JobSkill.skill), selectinload(Job.tenant))
        .execution_options(populate_existing=True)
    )
    if job is None:  # pragma: no cover - just written
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


async def list_jobs(db: AsyncSession, tenant_id: uuid.UUID) -> list[Job]:
    """This organisation's listings, drafts included."""
    return list(
        (
            await db.scalars(
                select(Job)
                .where(Job.tenant_id == tenant_id)
                .options(
                    selectinload(Job.skills).selectinload(JobSkill.skill),
                    selectinload(Job.tenant),
                )
                .order_by(Job.updated_at.desc())
            )
        ).all()
    )


async def get_job(db: AsyncSession, tenant_id: uuid.UUID, slug: str) -> Job:
    """404, never 403, on someone else's listing — a 403 confirms it exists."""
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return await _load(db, job.id)


async def create_job(db: AsyncSession, tenant_id: uuid.UUID, payload: JobIn) -> Job:
    location = await resolve_location(db, payload.location_state, payload.location_district)
    job = Job(
        slug=await _unique_slug(db, payload.title_en, payload.location_district),
        tenant_id=tenant_id,
        # Explicit. `Job.status` defaults to "published" at the model level, so
        # omitting this would put an unfinished listing straight in front of
        # candidates.
        status="draft",
        state_id=location.state_id,
        district_id=location.district_id,
        **{f: getattr(payload, f) for f in _PLAIN_FIELDS},
    )
    db.add(job)
    await db.flush()
    await _write_skills(db, job, payload.skills)
    await db.commit()
    return await _load(db, job.id)


async def update_job(db: AsyncSession, tenant_id: uuid.UUID, slug: str, payload: JobIn) -> Job:
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    for field in _PLAIN_FIELDS:
        setattr(job, field, getattr(payload, field))
    location = await resolve_location(db, payload.location_state, payload.location_district)
    job.state_id, job.district_id = location.state_id, location.district_id
    # The slug is not regenerated. It is a published URL as soon as the job goes
    # live, and rewriting it on a title tweak breaks every link to it.
    await db.flush()
    await _write_skills(db, job, payload.skills)
    await db.commit()
    return await _load(db, job.id)


async def set_published(db: AsyncSession, tenant_id: uuid.UUID, slug: str, published: bool) -> Job:
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    if published:
        required = await db.scalar(select(JobSkill.id).where(JobSkill.job_id == job.id).limit(1))
        if required is None:
            # Not a nicety. Matching scores concept overlap, so a job requiring
            # nothing can never appear for anyone -- it would be published and
            # permanently unmatchable.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Add at least one required standard before publishing",
            )

    job.status = "published" if published else "draft"
    await db.commit()
    return await _load(db, job.id)


async def delete_job(db: AsyncSession, tenant_id: uuid.UUID, slug: str) -> None:
    job = await db.scalar(select(Job).where(Job.slug == slug, Job.tenant_id == tenant_id))
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    await db.delete(job)
    await db.commit()
