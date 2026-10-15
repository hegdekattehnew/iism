import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity import User
from api.modules.notifications import devices, service
from api.modules.notifications.schemas import DeviceIn, DeviceRemoveIn, NotificationOut

router = APIRouter(prefix="/me/notifications", tags=["notifications"])
devices_router = APIRouter(prefix="/me/devices", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def my_notifications(
    limit: int = Query(50, ge=1, le=100),
    before: datetime | None = Query(
        None, description="Return notices older than this time (the last one of the previous page)."
    ),
    before_id: uuid.UUID | None = Query(
        None,
        description="With `before`: the last notice's id, so same-time notices stay.",
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[NotificationOut]:
    """In-app notices for the caller. Most candidates have no email address, so
    this is the channel that actually reaches them (ADR-038 left phone sign-in
    without one, and SMS waits on DLT registration)."""
    return [
        NotificationOut.model_validate(n)
        for n in await service.list_for(
            db, user.id, limit=limit, before=before, before_id=before_id
        )
    ]


@router.get("/unread-count", response_model=dict[str, int])
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    """What the header's count shows. One indexed count, cheap enough to ask on every page."""
    return {"unread": await service.unread_count(db, user.id)}


@router.post("/read", response_model=dict[str, int])
async def mark_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    return {"marked": await service.mark_all_read(db, user.id)}


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_one_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    if not await service.mark_read(db, user.id, notification_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")


@devices_router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def register_device(
    payload: DeviceIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """The phone says: send my pushes here. Called when somebody signs in on the app; moves the
    token if another account held it (ADR-075)."""
    await devices.register(
        db, user.id, token=payload.token, platform=payload.platform, locale=payload.locale
    )


@devices_router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    payload: DeviceRemoveIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Called while still signed in, as the person signs out. A POST with a body, not a DELETE
    with the token in the path: an Expo token contains brackets. Idempotent."""
    await devices.unregister(db, user.id, payload.token)
