"""Batches (Sprint 98, ADR-103).

Every route hangs off the **acting organisation's** slug, where `require()` has resolved the
membership and answers a stranger with 404 (ADR-038). The acting tenant is either a delivering
organisation (it reaches every batch of every one of its centres) or a centre (its own manager
reaches only that centre's batches); the service applies that scope, so a batch of another
organisation is the same 404 as one that does not exist.

The literal paths are declared before `/{batch_id}`.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.batches import service
from api.modules.batches.schemas import (
    BatchIn,
    BatchList,
    BatchOut,
    BatchUpdateIn,
    DeliverableCourses,
)

router = APIRouter(prefix="/org/{org_slug}/batches", tags=["batches"])

CanReadBatches = Depends(require(Permission.BATCH_READ, "batch"))
CanManageBatches = Depends(require(Permission.BATCH_MANAGE, "batch"))


@router.get("", response_model=BatchList)
async def list_batches(
    phase: Literal["draft", "open", "full", "running", "finished", "cancelled"] | None = None,
    centre: str | None = Query(default=None, max_length=200),
    course: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=25, ge=1, le=service.PAGE_MAX),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = CanReadBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchList:
    return await service.list_batches(
        db,
        context.tenant,
        phase=phase,
        centre_slug=centre,
        course_slug=course,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
async def create_batch(
    payload: BatchIn,
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.create_batch(db, context.tenant, context.user, payload)


@router.get("/courses", response_model=DeliverableCourses)
async def deliverable_courses(
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> DeliverableCourses:
    """The courses a batch can be made of: this organisation's own, and those it is authorised to
    deliver. **Planning's, not reading's**: it names other organisations' arrangements, which a
    centre's manager (who reads their centre's batches) has no part in."""
    return await service.deliverable_courses(db, context.tenant)


@router.get("/{batch_id}", response_model=BatchOut)
async def get_batch(
    batch_id: uuid.UUID,
    context: TenantContext = CanReadBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.get_batch(db, context.tenant, batch_id)


@router.put("/{batch_id}", response_model=BatchOut)
async def update_batch(
    batch_id: uuid.UUID,
    payload: BatchUpdateIn,
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.update_batch(db, context.tenant, batch_id, payload)


@router.post("/{batch_id}/publish", response_model=BatchOut)
async def publish_batch(
    batch_id: uuid.UUID,
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.publish_batch(db, context.tenant, context.user, batch_id)


@router.post("/{batch_id}/cancel", response_model=BatchOut)
async def cancel_batch(
    batch_id: uuid.UUID,
    context: TenantContext = CanManageBatches,
    db: AsyncSession = Depends(get_db_session),
) -> BatchOut:
    return await service.cancel_batch(db, context.tenant, context.user, batch_id)
