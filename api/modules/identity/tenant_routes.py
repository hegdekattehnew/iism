"""An organisation reading and editing itself.

In `identity/` rather than `marketplace/`, because a tenant is an identity
concept — `marketplace` consumes it through a foreign key and should not own
its lifecycle (ADR-010, ADR-014).

Until now there was **no tenant update surface anywhere**: an organisation's
name was fixed at the moment of creation and could never be corrected.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity import capabilities, schemas, service
from api.modules.identity.models import User

router = APIRouter(prefix="/org/{org_slug}", tags=["organisations"])

CanRead = Depends(require(Permission.ORG_READ))
CanUpdate = Depends(require(Permission.ORG_UPDATE))


@router.get("", response_model=schemas.OrganisationOut)
async def get_organisation(context: TenantContext = CanRead) -> schemas.OrganisationOut:
    """The members' view, which carries the contact address the public one omits."""
    return schemas.OrganisationOut.model_validate(context.tenant)


@router.put("", response_model=schemas.OrganisationOut)
async def update_organisation(
    payload: schemas.OrganisationIn,
    context: TenantContext = CanUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrganisationOut:
    """Owner only.

    `slug`, `tenant_type` and `is_verified` are absent from `OrganisationIn`, so
    they cannot be set here however the request is shaped: the slug is a
    published URL, changing the type would strand listings already published
    under it, and verification is ours to assert rather than theirs to claim.
    """
    tenant = await service.update_organisation(
        db, context.tenant, payload.model_dump(exclude_unset=True)
    )
    return schemas.OrganisationOut.model_validate(tenant)


@router.put("/capabilities", response_model=schemas.OrganisationOut)
async def set_capabilities(
    payload: schemas.CapabilitiesIn,
    context: TenantContext = CanUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.OrganisationOut:
    """Owner only: whether this training organisation sells courses, delivers training, or both.

    Refused (409) for an employer, for a change that would leave it doing neither, and while it has
    published courses or anything that delivering means (ADR-102). The change is recorded.
    """
    tenant = await capabilities.set_capabilities(
        db,
        tenant=context.tenant,
        actor=user,
        sells_courses=payload.sells_courses,
        delivers_training=payload.delivers_training,
    )
    return schemas.OrganisationOut.model_validate(tenant)
