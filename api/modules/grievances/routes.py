import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import OperatorContext, Permission, require_operator
from api.core.database import get_db_session
from api.core.localisation import negotiate
from api.core.middleware import client_ip
from api.core.security import get_current_user, get_optional_user
from api.modules.grievances import schemas, service
from api.modules.grievances.models import Grievance
from api.modules.identity.models import User

# Anyone, signed in or not. The one public endpoint that writes a row, so it has a budget, a
# honeypot and a length cap (see the service), and it is named in `PUBLIC_ROUTES` with its reason.
router = APIRouter(prefix="/grievances", tags=["grievances"])
# A signed-in person's own messages.
me_router = APIRouter(prefix="/me/grievances", tags=["grievances"])
# The back office. Permission, never a role (ADR-039).
ops_router = APIRouter(prefix="/ops/grievances", tags=["operations"])

CanRead = Depends(require_operator(Permission.OPS_GRIEVANCE_READ))
CanHandle = Depends(require_operator(Permission.OPS_GRIEVANCE_HANDLE))


@router.post("", response_model=schemas.GrievanceSubmittedOut, status_code=status.HTTP_201_CREATED)
async def send(
    payload: schemas.GrievanceIn,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    user: User | None = Depends(get_optional_user),
) -> schemas.GrievanceSubmittedOut:
    """Send us a message: a question, a complaint, or a request about your data.

    A request about your data needs you signed in. Anything else may be sent by a stranger, who
    must give an address to write back to; we never write to it ourselves.
    """
    locale = negotiate(
        request.headers.get("accept-language"), None, user.preferred_locale if user else None
    )
    return await service.submit(
        db, payload, user=user, client=client_ip(request.scope), locale=locale
    )


@me_router.get("", response_model=list[schemas.GrievanceOut])
async def my_messages(
    db: AsyncSession = Depends(get_db_session), user: User = Depends(get_current_user)
) -> list[schemas.GrievanceOut]:
    return [
        schemas.GrievanceOut(
            reference=g.reference,
            kind=g.kind,
            status=g.status,
            created_at=g.created_at,
            acknowledged_at=g.acknowledged_at,
            resolved_at=g.resolved_at,
        )
        for g in await service.mine(db, user)
    ]


@ops_router.get("", response_model=schemas.GrievanceQueueOut)
async def queue(
    status_filter: Literal["open", "acknowledged", "resolved", "dismissed"] | None = Query(
        None, alias="status"
    ),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanRead,
) -> schemas.GrievanceQueueOut:
    return await service.queue(db, status_filter=status_filter, limit=limit)


@ops_router.post("/{grievance_id}/acknowledge", response_model=schemas.GrievanceOut)
async def acknowledge(
    grievance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanHandle,
) -> schemas.GrievanceOut:
    return _out(await service.acknowledge(db, grievance_id, actor=context.user))


@ops_router.post("/{grievance_id}/resolve", response_model=schemas.GrievanceOut)
async def resolve(
    grievance_id: uuid.UUID,
    payload: schemas.GrievanceDecisionIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanHandle,
) -> schemas.GrievanceOut:
    return _out(
        await service.close(
            db, grievance_id, outcome="resolved", note=payload.note, actor=context.user
        )
    )


@ops_router.post("/{grievance_id}/dismiss", response_model=schemas.GrievanceOut)
async def dismiss(
    grievance_id: uuid.UUID,
    payload: schemas.GrievanceDecisionIn,
    db: AsyncSession = Depends(get_db_session),
    context: OperatorContext = CanHandle,
) -> schemas.GrievanceOut:
    return _out(
        await service.close(
            db, grievance_id, outcome="dismissed", note=payload.note, actor=context.user
        )
    )


def _out(g: Grievance) -> schemas.GrievanceOut:
    return schemas.GrievanceOut(
        reference=g.reference,
        kind=g.kind,
        status=g.status,
        created_at=g.created_at,
        acknowledged_at=g.acknowledged_at,
        resolved_at=g.resolved_at,
    )
