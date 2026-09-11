from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity import User
from api.modules.privacy import service
from api.modules.privacy.schemas import DeletionPreview

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
