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

from api.core.authorization import Permission, TenantContext, require
from api.core.config import get_settings
from api.core.database import get_db_session
from api.modules.analytics import record
from api.modules.identity.models import Tenant
from api.modules.marketplace.models import CandidateSkill
from api.modules.matching import employer, schemas

# The demonstration console: no authentication, local environments only.
router = APIRouter(prefix="/employer", tags=["employer"])

# The real one: same service layer, same de-identified payload, but the
# organisation is named by the path and granted by the caller's membership
# (ADR-039). This ships to production; the router above does not.
org_router = APIRouter(prefix="/org/{org_slug}/candidates", tags=["employer"])
# `"job"` because a shortlist is candidates for *their vacancies*: a training
# provider has none, and used to get a 200 here carrying a global candidate
# count. The dependency asks both questions so a handler cannot forget one.
CanShortlist = Depends(require(Permission.CANDIDATE_SHORTLIST, "job"))


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


async def _overview(db: AsyncSession, tenant: Tenant) -> schemas.EmployerOverview:
    """Shared by the demonstration and the authenticated console.

    Both surfaces answer the same question and must answer it identically; two
    implementations would drift, and the demo would stop being a demonstration
    of the real thing.
    """
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


async def _ranking(
    db: AsyncSession, tenant: Tenant, job_slug: str, limit: int
) -> schemas.CandidateRanking:
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


@router.get("/{slug}/overview", response_model=schemas.EmployerOverview)
async def overview(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.EmployerOverview:
    """Every open vacancy, the pool against each, and what the pool cannot supply."""
    tenant = await employer.get_employer(db, slug)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employer not found")
    return await _overview(db, tenant)


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
    return await _ranking(db, tenant, job_slug, limit)


# --------------------------------------------------- the authenticated console


@org_router.get("", response_model=schemas.EmployerOverview)
async def org_overview(
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.EmployerOverview:
    """The signed-in employer's own vacancies and the pool against each.

    Employers only. A training provider used to get a 200 here carrying two
    empty arrays and `candidates_total`, which has no tenant filter -- so the
    one number on the screen was a global count of every candidate on the
    platform, presented as though it were a pool they had access to.
    """
    return await _overview(db, context.tenant)


@org_router.get("/{job_slug}", response_model=schemas.CandidateRanking)
async def org_candidates(
    job_slug: str,
    limit: int = Query(20, ge=1, le=50),
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateRanking:
    return await _ranking(db, context.tenant, job_slug, limit)


def mount_employer_console(app: object) -> bool:
    """Mount the *demonstration* console in local environments only.

    An allowlist, not a production denylist. The earlier version compared to
    `"production"` alone, which mounted an unauthenticated reader of the
    candidate pool on `staging`, on `ci`, and on any host where `ENVIRONMENT`
    was unset or misspelled. `settings.is_local` is the same guard the demo
    task router already uses.

    The authenticated console (`org_router`) is mounted unconditionally by
    `api/main.py`; it needs no guard, because it has authentication.
    """
    if not get_settings().is_local:
        return False
    app.include_router(router)  # type: ignore[attr-defined]
    return True
