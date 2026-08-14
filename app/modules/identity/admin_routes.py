from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.permissions import require_platform_role
from app.modules.identity import admin_service
from app.modules.identity.schemas import AdminOrganizationInviteRequest, StaffInviteRequest

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/organizations", status_code=status.HTTP_202_ACCEPTED)
async def invite_organization(
    data: AdminOrganizationInviteRequest,
    db: AsyncSession = Depends(get_db_session),
    _: object = Depends(require_platform_role("admin", "super_admin")),
) -> None:
    await admin_service.invite_organization(db, data)


@router.post("/staff", status_code=status.HTTP_202_ACCEPTED)
async def invite_staff(
    data: StaffInviteRequest,
    db: AsyncSession = Depends(get_db_session),
    _: object = Depends(require_platform_role("super_admin")),
) -> None:
    await admin_service.invite_staff(db, data)
