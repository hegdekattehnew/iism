"""The employer console's endpoints — a demonstration surface, and labelled one.

Unauthenticated on purpose, and mounted only outside production. Sprint 4
deferred organisation login because organisations had nothing to publish, and
that is still true; assuming an employer identity for a demonstration is
honest, dressing it up as authentication is not. What is *not* acceptable is a
demonstration that quietly ships, so `mount_employer_console` refuses to mount
in production rather than trusting a future reader to notice.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.core.database import get_db_session
from api.modules.analytics import record
from api.modules.marketplace.models import CandidateSkill
from api.modules.matching import employer, schemas

router = APIRouter(prefix="/employer", tags=["employer"])


def _card(scored: employer.ScoredCandidate) -> schemas.CandidateCardOut:
    p, r = scored.profile, scored.result
    return schemas.CandidateCardOut(
        # A stable handle with no personal data in it. Enough to refer to a
        # candidate across a conversation; not enough to identify one.
        reference=f"C-{str(p.id)[:8].upper()}",
        headline=p.headline,
        location_state=p.location_state,
        location_district=p.location_district,
        years_experience=p.years_experience,
        score=r.score,
        coverage=round(r.coverage, 4),
        matched=[schemas.MatchedSkillOut(**vars(m)) for m in r.matched],
        missing=[
            schemas.MissingSkillOut(
                skill_id=m.skill_id,
                nos_code=m.nos_code,
                name_en=m.name_en,
                importance=m.importance,
                is_mandatory=m.is_mandatory,
                nsqf_level=float(m.nsqf_level) if m.nsqf_level is not None else None,
            )
            for m in r.missing
        ],
        missing_mandatory=r.missing_mandatory,
        level_shortfall=float(r.level_shortfall) if r.level_shortfall is not None else None,
        capped_by_mandatory=r.capped_by_mandatory,
    )


@router.get("/employers", response_model=list[schemas.EmployerOut])
async def list_employers(
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.EmployerOut]:
    """Employers with something published, for the demonstration's picker."""
    return [schemas.EmployerOut.model_validate(t) for t in await employer.list_employers(db)]


@router.get("/{slug}/overview", response_model=schemas.EmployerOverview)
async def overview(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.EmployerOverview:
    """Every open vacancy, the pool against each, and what the pool cannot supply."""
    tenant = await employer.get_employer(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employer not found")

    pools = await employer.job_pools(db, tenant.id)
    scarce = await employer.scarce_skills(db, tenant.id)
    # Candidates who have declared something, not registered accounts. An empty
    # profile is not a candidate an employer could ever be shown.
    total = await db.scalar(select(func.count(func.distinct(CandidateSkill.profile_id)))) or 0

    await record(
        db,
        "employer_overview_viewed",
        subject_type="tenant",
        subject_id=tenant.id,
        payload={"jobs": len(pools)},
    )
    return schemas.EmployerOverview(
        employer=schemas.EmployerOut.model_validate(tenant),
        jobs=[
            schemas.JobPoolOut(
                job=schemas.JobSummary.model_validate(p.job),
                pool=p.pool,
                ready=p.ready,
                nearly=p.nearly,
            )
            for p in pools
        ],
        scarce=[schemas.ScarceSkillOut(**vars(s)) for s in scarce],
        candidates_total=total,
    )


@router.get("/{slug}/jobs/{job_slug}/candidates", response_model=schemas.CandidateRanking)
async def candidates(
    slug: str,
    job_slug: str,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateRanking:
    """Ranked candidates for one vacancy, each with the gap that placed them."""
    tenant = await employer.get_employer(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employer not found")

    found = await employer.rank_candidates(db, tenant.id, job_slug, limit=limit)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    job, scored = found

    await record(
        db,
        "employer_shortlist_viewed",
        subject_type="job",
        subject_id=job.id,
        payload={"returned": len(scored)},
    )
    return schemas.CandidateRanking(
        job=schemas.JobSummary.model_validate(job),
        items=[_card(s) for s in scored],
        total=len(scored),
    )


def mount_employer_console(app: object) -> bool:
    """Mount the console outside production only. Returns whether it mounted.

    Mirrors `ConsoleNotificationProvider`, which refuses to run in production
    for the same reason: a stand-in that survives into a live environment is
    indistinguishable from the real thing right up until it matters.
    """
    if get_settings().environment == "production":
        return False
    app.include_router(router)  # type: ignore[attr-defined]
    return True
