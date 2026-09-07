"""The employer's own listings.

Every route here names its organisation in the path and is granted it by the
caller's membership (ADR-039). The tenant id is never read from a request body:
that is the difference between an organisation you belong to and one you named.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.marketplace import publishing, schemas

router = APIRouter(prefix="/org/{org_slug}/jobs", tags=["publishing"])

# Built once at import, then used as argument defaults. `Depends(require(...))`
# inline is the same thing, but constructing the dependency on every call is
# both wasteful and what B008 exists to catch.
CanRead = Depends(require(Permission.ORG_READ))
CanCreate = Depends(require(Permission.JOB_CREATE))
CanUpdate = Depends(require(Permission.JOB_UPDATE))
CanPublish = Depends(require(Permission.JOB_PUBLISH))
CanDelete = Depends(require(Permission.JOB_DELETE))


@router.get("", response_model=list[schemas.OrgJobOut])
async def list_jobs(
    context: TenantContext = CanRead,
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.OrgJobOut]:
    """Drafts included. Every public listing query filters on published, so this
    is the only place an unfinished vacancy is visible at all."""
    jobs = await publishing.list_jobs(db, context.tenant.id)
    return [schemas.OrgJobOut.model_validate(j) for j in jobs]


@router.post("", response_model=schemas.OrgJobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: schemas.JobIn,
    context: TenantContext = CanCreate,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgJobOut:
    job = await publishing.create_job(db, context.tenant.id, payload)
    return schemas.OrgJobOut.model_validate(job)


@router.get("/{slug}", response_model=schemas.OrgJobOut)
async def get_job(
    slug: str,
    context: TenantContext = CanRead,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgJobOut:
    job = await publishing.get_job(db, context.tenant.id, slug)
    return schemas.OrgJobOut.model_validate(job)


@router.put("/{slug}", response_model=schemas.OrgJobOut)
async def update_job(
    slug: str,
    payload: schemas.JobIn,
    context: TenantContext = CanUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgJobOut:
    job = await publishing.update_job(db, context.tenant.id, slug, payload)
    return schemas.OrgJobOut.model_validate(job)


@router.post("/{slug}/publish", response_model=schemas.OrgJobOut)
async def publish_job(
    slug: str,
    context: TenantContext = CanPublish,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgJobOut:
    """Explicit, and refused for a job requiring no standards."""
    job = await publishing.set_published(db, context.tenant.id, slug, True)
    return schemas.OrgJobOut.model_validate(job)


@router.post("/{slug}/unpublish", response_model=schemas.OrgJobOut)
async def unpublish_job(
    slug: str,
    context: TenantContext = CanPublish,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrgJobOut:
    job = await publishing.set_published(db, context.tenant.id, slug, False)
    return schemas.OrgJobOut.model_validate(job)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    slug: str,
    context: TenantContext = CanDelete,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Owner only. An admin can unpublish, which reverses; this does not."""
    await publishing.delete_job(db, context.tenant.id, slug)
