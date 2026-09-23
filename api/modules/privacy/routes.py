from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity import User
from api.modules.privacy import service
from api.modules.privacy.schemas import DeletionPreview, OrganisationDeletionPreview

# `get_current_user`, not `get_current_candidate`: an organisation-only account
# has exactly the same rights over its own data as a job seeker.
router = APIRouter(prefix="/me/account", tags=["privacy"])


@router.get("/export")
async def export_my_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Everything held about the caller, as one JSON document (DPDP Act 2023)."""
    return await service.export_account(db, user)


@router.get("/deletion", response_model=DeletionPreview)
async def preview_deletion(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DeletionPreview:
    """What deleting this account would take with it. Changes nothing."""
    return await service.deletion_preview(db, user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Erase the account. Irreversible; the client shows the preview first."""
    await service.delete_account(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Deleting one organisation lives here rather than in `identity/`, because
# `_delete_tenant` -- the single function that knows everything a tenant owns
# -- lives here, and a second copy of that knowledge is how one of its eleven
# tables starts being missed. It also keeps ADR-014's rule intact: privacy
# depends on every module and nothing depends on privacy.
org_router = APIRouter(prefix="/org/{org_slug}", tags=["privacy"])

# `require()` with no `publishes` argument: deleting an organisation is not a
# publishing act, and an employer and a training provider delete theirs the
# same way. A non-member still gets 404 rather than 403 (ADR-038).
CanDeleteOrg = Depends(require(Permission.ORG_DELETE))


@org_router.get("/deletion", response_model=OrganisationDeletionPreview)
async def preview_organisation_deletion(
    context: TenantContext = CanDeleteOrg,
    db: AsyncSession = Depends(get_db_session),
) -> OrganisationDeletionPreview:
    """What deleting this organisation would take with it. Changes nothing."""
    return await service.organisation_deletion_preview(db, context.tenant, context.user)


@org_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organisation(
    context: TenantContext = CanDeleteOrg,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Delete this organisation. **The account and its other organisations are
    untouched.**

    Owner only, and irreversible. The client shows the preview first, because
    the part an owner does not think of is the applications -- those belong to
    somebody else, and the people still waiting are told.
    """
    await service.delete_organisation(db, context.user, context.tenant)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
