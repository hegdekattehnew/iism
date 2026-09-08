"""A training provider's own listings.

Mirrors `publishing_routes.py`. Every route names its organisation in the path
and is granted it by the caller's membership (ADR-039), and every **write**
dependency also names what it publishes — membership answers *may this person
act here*, never *is this the right kind of organisation*. Both questions are one
declaration, so a handler cannot answer the first and forget the second.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.marketplace import course_publishing, schemas

router = APIRouter(prefix="/org/{org_slug}/courses", tags=["publishing"])

# Built once at import: `Depends(require(...))` inline rebuilds the dependency
# on every call, which is what B008 exists to catch.
CanRead = Depends(require(Permission.ORG_READ))
CanCreate = Depends(require(Permission.COURSE_CREATE, "course"))
CanUpdate = Depends(require(Permission.COURSE_UPDATE, "course"))
CanPublish = Depends(require(Permission.COURSE_PUBLISH, "course"))
CanDelete = Depends(require(Permission.COURSE_DELETE, "course"))


@router.get("", response_model=list[schemas.OrgCourseOut])
async def list_courses(
    context: TenantContext = CanRead,
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.OrgCourseOut]:
    """Drafts included. Every public listing query filters on published, so this
    is the only place an unfinished course is visible at all."""
    return [
        schemas.OrgCourseOut.model_validate(c)
        for c in await course_publishing.list_courses(db, context.tenant.id)
    ]


@router.post("", response_model=schemas.OrgCourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: schemas.CourseIn,
    context: TenantContext = CanCreate,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgCourseOut:
    course = await course_publishing.create_course(db, context.tenant.id, payload)
    return schemas.OrgCourseOut.model_validate(course)


@router.get("/{slug}", response_model=schemas.OrgCourseOut)
async def get_course(
    slug: str,
    context: TenantContext = CanRead,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgCourseOut:
    course = await course_publishing.get_course(db, context.tenant.id, slug)
    return schemas.OrgCourseOut.model_validate(course)


@router.put("/{slug}", response_model=schemas.OrgCourseOut)
async def update_course(
    slug: str,
    payload: schemas.CourseIn,
    context: TenantContext = CanUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgCourseOut:
    course = await course_publishing.update_course(db, context.tenant.id, slug, payload)
    return schemas.OrgCourseOut.model_validate(course)


@router.post("/{slug}/publish", response_model=schemas.OrgCourseOut)
async def publish_course(
    slug: str,
    context: TenantContext = CanPublish,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgCourseOut:
    """Explicit, and refused for a course teaching no standards."""
    course = await course_publishing.set_published(db, context.tenant.id, slug, True)
    return schemas.OrgCourseOut.model_validate(course)


@router.post("/{slug}/unpublish", response_model=schemas.OrgCourseOut)
async def unpublish_course(
    slug: str,
    context: TenantContext = CanPublish,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgCourseOut:
    course = await course_publishing.set_published(db, context.tenant.id, slug, False)
    return schemas.OrgCourseOut.model_validate(course)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    slug: str,
    context: TenantContext = CanDelete,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Owner only. An admin can unpublish, which reverses; this does not."""
    await course_publishing.delete_course(db, context.tenant.id, slug)
