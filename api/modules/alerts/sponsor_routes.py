"""Hire and train, for an employer (ADR-048).

Under the same prefix and permission as the console's candidate pool: it is the
same screen, and the same organisation-scoped question of who may see it.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.alerts import sponsorship
from api.modules.alerts.schemas import SponsorOut, TrainingOut
from api.modules.matching.schemas import CourseSuggestionOut, MissingSkillOut

router = APIRouter(prefix="/org/{org_slug}/candidates", tags=["employer"])

# `"job"` because a candidate pool is for *their vacancies*: a training provider
# has none, and the dependency asks both questions so a handler cannot forget one.
CanShortlist = Depends(require(Permission.CANDIDATE_SHORTLIST, "job"))


@router.get("/{job_slug}/{reference}/training", response_model=TrainingOut)
async def training(
    job_slug: str,
    reference: str,
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> TrainingOut:
    """The courses that teach the one standard this candidate is missing."""
    offer = await sponsorship.training_for(db, context.tenant.id, job_slug, reference)
    return TrainingOut(
        reference=offer.reference,
        standard=MissingSkillOut.from_missing(offer.standard),
        courses=[CourseSuggestionOut.from_suggestion(c) for c in offer.courses],
        offered=offer.offered,
    )


@router.post(
    "/{job_slug}/{reference}/sponsor",
    response_model=SponsorOut,
    status_code=status.HTTP_201_CREATED,
)
async def sponsor(
    job_slug: str,
    reference: str,
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> SponsorOut:
    """Offer to sponsor that standard. The candidate is told if they may be."""
    await sponsorship.offer(db, context.tenant, job_slug, reference, actor_user_id=context.user.id)
    return SponsorOut()
