import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import OperatorContext, Permission, require_operator
from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity.models import User
from api.modules.moderation import schemas, service

# A signed-in person tells us a listing is wrong. The listing's page is public; reporting it is not
# (an accountable report, and a budget per person), so these are not in `PUBLIC_ROUTES`.
router = APIRouter(tags=["moderation"])
# The back office. Permission, never a role (ADR-039).
ops_router = APIRouter(prefix="/ops", tags=["operations"])

CanRead = Depends(require_operator(Permission.OPS_REPORT_READ))
CanDismiss = Depends(require_operator(Permission.OPS_REPORT_HANDLE))
CanTakeDown = Depends(require_operator(Permission.OPS_LISTING_TAKEDOWN))


@router.post(
    "/jobs/{slug}/report",
    response_model=schemas.ReportReceivedOut,
    status_code=status.HTTP_201_CREATED,
)
async def report_job(
    slug: str,
    payload: schemas.ReportIn,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.ReportReceivedOut:
    """Tell us a vacancy is fake, misleading or harmful. Once per vacancy, and not your own."""
    await service.submit_report(db, user, "job", slug, payload)
    return schemas.ReportReceivedOut()


@router.post(
    "/courses/{slug}/report",
    response_model=schemas.ReportReceivedOut,
    status_code=status.HTTP_201_CREATED,
)
async def report_course(
    slug: str,
    payload: schemas.ReportIn,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.ReportReceivedOut:
    await service.submit_report(db, user, "course", slug, payload)
    return schemas.ReportReceivedOut()


@ops_router.get("/reports", response_model=schemas.ReportQueueOut)
async def queue(
    view: Literal["open", "taken_down"] = "open",
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanRead,
) -> schemas.ReportQueueOut:
    return await service.queue(db, view=view, limit=limit)


@ops_router.post("/reports/{target_type}/{target_id}/dismiss", response_model=schemas.DecisionOut)
async def dismiss(
    target_type: schemas.TargetType,
    target_id: uuid.UUID,
    payload: schemas.DismissIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanDismiss,
) -> schemas.DecisionOut:
    closed = await service.dismiss(db, target_type, target_id, actor=context.user)
    return schemas.DecisionOut(
        target_type=target_type, target_id=target_id, reports_closed=closed, taken_down=False
    )


@ops_router.post("/listings/{target_type}/{target_id}/takedown", response_model=schemas.DecisionOut)
async def takedown(
    target_type: schemas.TargetType,
    target_id: uuid.UUID,
    payload: schemas.TakedownIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanTakeDown,
) -> schemas.DecisionOut:
    closed = await service.takedown(db, target_type, target_id, payload.reason, actor=context.user)
    return schemas.DecisionOut(
        target_type=target_type, target_id=target_id, reports_closed=closed, taken_down=True
    )


@ops_router.post("/listings/{target_type}/{target_id}/restore", response_model=schemas.DecisionOut)
async def restore(
    target_type: schemas.TargetType,
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanTakeDown,
) -> schemas.DecisionOut:
    await service.restore(db, target_type, target_id, actor=context.user)
    return schemas.DecisionOut(target_type=target_type, target_id=target_id, taken_down=False)
