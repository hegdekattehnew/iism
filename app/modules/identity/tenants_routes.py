import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.permissions import require_tenant_role_path
from app.modules.identity import service_accounts
from app.modules.identity.schemas import ServiceAccountCreateRequest, ServiceAccountCreateResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "/{tenant_id}/service-accounts",
    response_model=ServiceAccountCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_account(
    tenant_id: uuid.UUID,
    data: ServiceAccountCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: object = Depends(require_tenant_role_path("owner")),
) -> ServiceAccountCreateResponse:
    account, api_key = await service_accounts.create_service_account(db, tenant_id, data.name)
    return ServiceAccountCreateResponse(id=account.id, name=account.name, api_key=api_key)
