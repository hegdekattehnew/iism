"""A training provider's own question: does my course cover this role?

Sibling of `employer_routes.py`'s `org_router` -- same shape, a different
tenant type. The organisation is named by the path and granted by the
caller's membership (ADR-039); there is no course-type check beyond that
because `get_org_course` already scopes to the caller's own tenant, so an
employer asking about a course slug that belongs to someone else simply gets
"course not found" (404, never 403 -- ADR-038).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.marketplace import get_org_course
from api.modules.matching import schemas
from api.modules.matching.service import course_role_alignment

org_router = APIRouter(prefix="/org/{org_slug}/courses/{course_slug}/alignment", tags=["provider"])
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
