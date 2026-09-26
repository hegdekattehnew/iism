"""A training provider's own two questions: does my course cover this role,
and what does the market broadly need that the pool cannot supply?

Sibling of `employer_routes.py`'s `org_router` -- same shape, a different
tenant type. The organisation is named by the path and granted by the
caller's membership (ADR-039); there is no course-type check beyond that
because `get_org_course` already scopes to the caller's own tenant, so an
employer asking about a course slug that belongs to someone else simply gets
"course not found" (404, never 403 -- ADR-038). `market_router` needs no such
scoping at all -- market demand is the same answer for every caller, which is
the whole point of it (BL-2.4).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.marketplace import get_org_course
from api.modules.matching import schemas
from api.modules.matching.employer import market_scarce_skills
from api.modules.matching.service import course_role_alignment

org_router = APIRouter(prefix="/org/{org_slug}/courses/{course_slug}/alignment", tags=["provider"])
market_router = APIRouter(prefix="/org/{org_slug}/market-demand", tags=["provider"])
CanRead = Depends(require(Permission.ORG_READ))


@org_router.get("/{role_slug}", response_model=schemas.CourseRoleAlignmentOut)
async def alignment_with_role(
    course_slug: str,
    role_slug: str,
    context: TenantContext = CanRead,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CourseRoleAlignmentOut:
    """How much of one role's compulsory requirement this course teaches.

    Independent of any candidate (BL-2.3): a provider deciding whether to
    build or adjust a course, not a hiring decision. `role_slug` is a
    qualification pack's slug, the same one `GET /roles/{slug}/standards`
    already resolves.
    """
    course = await get_org_course(db, context.tenant.id, course_slug)
    alignment = await course_role_alignment(db, course, role_slug)
    if alignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")

    return schemas.CourseRoleAlignmentOut(
        course_slug=course.slug,
        course_title=course.title,
        role_slug=role_slug,
        role_name=alignment.role_name,
        qualification_code=alignment.qp.qp_code,
        covered=alignment.covered,
        missing=alignment.missing,
        required_count=alignment.required_count,
        coverage_percent=round(alignment.coverage_ratio * 100),
    )


@market_router.get("", response_model=list[schemas.ScarceSkillOut])
async def market_demand(
    limit: int = Query(8, ge=1, le=50),
    context: TenantContext = CanRead,
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.ScarceSkillOut]:
    """Which standards the whole market wants that the candidate pool cannot
    supply (Sprint 33, BL-2.4) -- the demand-side mirror of the employer
    console's `scarce_skills`, not scoped to this provider's own courses.

    `context` establishes that a signed-in member of *some* organisation is
    asking; the answer itself is the same for every caller, employer or
    provider alike, because market scarcity is a fact about the platform, not
    about who is looking at it.
    """
    return [schemas.ScarceSkillOut(**vars(s)) for s in await market_scarce_skills(db, limit=limit)]
