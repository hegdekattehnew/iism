"""Delivering somebody else's course (Sprint 97, ADR-102, BL-18.15).

Everything an organisation does hangs off its own slug (`/org/{org}/delivery`), where `require()`
has resolved its membership and answers a stranger with 404. Which side of an arrangement an
organisation is on is a **capability**, not a role: asking to deliver needs `delivers_training`,
inviting and approving need `publishes_courses`, and ending one is open to either (the service
checks the organisation is a party to the row).

The two public reads (`/training-organisations`, `/providers/{slug}/delivery`) show only what the
public provider page already shows.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.modules.delivery import service
from api.modules.delivery.schemas import (
    AuthorisationOut,
    DeliveredOut,
    DeliveryAskIn,
    DeliveryOut,
    TrainingOrganisationList,
)

router = APIRouter(prefix="/org/{org_slug}/delivery", tags=["delivery"])
public_router = APIRouter(tags=["delivery"])

CanSeeDelivery = Depends(require(Permission.DELIVERY_READ, "delivery"))
CanDeliver = Depends(require(Permission.DELIVERY_MANAGE, "centre"))
CanSell = Depends(require(Permission.DELIVERY_MANAGE, "course"))
CanEnd = Depends(require(Permission.DELIVERY_MANAGE, "delivery"))


async def _one(db: AsyncSession, context: TenantContext, row_id: uuid.UUID) -> AuthorisationOut:
    """The arrangement as the acting organisation sees it, after it changed."""
    mine = await service.arrangements_of(db, context.tenant)
    for item in (*mine.as_partner, *mine.as_provider):
        if item.id == row_id:
            return item
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Arrangement not found")


@router.get("", response_model=DeliveryOut)
async def my_arrangements(
    context: TenantContext = CanSeeDelivery,
    db: AsyncSession = Depends(get_db_session),
) -> DeliveryOut:
    """Every arrangement this organisation is in, as the seller and as the one delivering."""
    return await service.arrangements_of(db, context.tenant)


@router.post("/requests", response_model=AuthorisationOut, status_code=status.HTTP_201_CREATED)
async def ask_to_deliver(
    payload: DeliveryAskIn,
    context: TenantContext = CanDeliver,
    db: AsyncSession = Depends(get_db_session),
) -> AuthorisationOut:
    """Ask a seller to let this organisation deliver one of its courses, or all of them."""
    row = await service.request_delivery(
        db,
        partner=context.tenant,
        actor=context.user,
        provider_slug=payload.organisation_slug,
        course_slug=payload.course_slug,
    )
    return await _one(db, context, row.id)


@router.post("/invitations", response_model=AuthorisationOut, status_code=status.HTTP_201_CREATED)
async def invite_to_deliver(
    payload: DeliveryAskIn,
    context: TenantContext = CanSell,
    db: AsyncSession = Depends(get_db_session),
) -> AuthorisationOut:
    """Authorise a delivering organisation to deliver one of this organisation's courses, or all."""
    row = await service.invite_partner(
        db,
        provider=context.tenant,
        actor=context.user,
        partner_slug=payload.organisation_slug,
        course_slug=payload.course_slug,
    )
    return await _one(db, context, row.id)


@router.post("/{authorisation_id}/approve", response_model=AuthorisationOut)
async def approve_request(
    authorisation_id: uuid.UUID,
    context: TenantContext = CanSell,
    db: AsyncSession = Depends(get_db_session),
) -> AuthorisationOut:
    """The seller says yes. 403 for the partner, 409 if it is no longer a request."""
    await service.approve(
        db, provider=context.tenant, actor=context.user, authorisation_id=authorisation_id
    )
    return await _one(db, context, authorisation_id)


@router.post("/{authorisation_id}/decline", response_model=AuthorisationOut)
async def decline_request(
    authorisation_id: uuid.UUID,
    context: TenantContext = CanEnd,
    db: AsyncSession = Depends(get_db_session),
) -> AuthorisationOut:
    """Close a request nobody has approved: refuse it (the seller) or withdraw it (the partner)."""
    await service.decline(
        db, org=context.tenant, actor=context.user, authorisation_id=authorisation_id
    )
    return await _one(db, context, authorisation_id)


@router.post("/{authorisation_id}/revoke", response_model=AuthorisationOut)
async def revoke_arrangement(
    authorisation_id: uuid.UUID,
    context: TenantContext = CanEnd,
    db: AsyncSession = Depends(get_db_session),
) -> AuthorisationOut:
    """End an approved arrangement. Either side may."""
    await service.revoke(
        db, org=context.tenant, actor=context.user, authorisation_id=authorisation_id
    )
    return await _one(db, context, authorisation_id)


@public_router.get("/training-organisations", response_model=TrainingOrganisationList)
async def training_organisations(
    q: str | None = Query(None, max_length=100),
    sells: bool = Query(False),
    delivers: bool = Query(False),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> TrainingOrganisationList:
    """Training organisations by name, slug or city, optionally only those that sell courses or
    deliver training: how an organisation finds the one to ask, or to invite."""
    return await service.search_organisations(db, q=q, sells=sells, delivers=delivers, limit=limit)


@public_router.get("/providers/{slug}/delivery", response_model=DeliveredOut)
async def authorised_to_deliver(
    slug: str, db: AsyncSession = Depends(get_db_session)
) -> DeliveredOut:
    """What this organisation is authorised to deliver for others, and whose each course is."""
    found = await service.authorised_to_deliver(db, slug)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    return found
