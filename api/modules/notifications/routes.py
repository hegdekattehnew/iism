from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity import User
from api.modules.notifications import service
from api.modules.notifications.schemas import NotificationOut

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def my_notifications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[NotificationOut]:
    """In-app notices for the caller. Most candidates have no email address, so
    this is the channel that actually reaches them (ADR-038 left phone sign-in
    without one, and SMS waits on DLT registration)."""
    return [NotificationOut.model_validate(n) for n in await service.unread_for(db, user.id)]


@router.post("/read", response_model=dict[str, int])
async def mark_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    return {"marked": await service.mark_all_read(db, user.id)}
