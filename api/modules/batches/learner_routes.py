"""The learner's routes (Sprint 100, ADR-103). The list and the detail are public; registering is
the candidate's (`get_current_candidate`: an organisation-only account must not be given a candidate
profile by pressing a button on a batch)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_optional_user
from api.modules.batches import learner
from api.modules.batches.schemas import (
    BatchInterestIn,
    BatchInterestOut,
    PublicBatchList,
    PublicBatchOut,
)
from api.modules.identity import User, get_current_candidate

public_router = APIRouter(prefix="/batches", tags=["batches-public"])
me_router = APIRouter(prefix="/me/batch-interests", tags=["batches-public"])


@public_router.get("", response_model=PublicBatchList)
async def public_batches(
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    starts_within: int | None = Query(default=None, ge=1, le=365),
    max_fee: int | None = Query(default=None, ge=0, le=10_000_000),
    course: str | None = Query(default=None, max_length=200),
    mode: Literal["in_person", "hybrid", "online"] | None = None,
    limit: int = Query(default=24, ge=1, le=learner.PAGE_MAX),
    offset: int = Query(default=0, ge=0),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> PublicBatchList:
    """Batches a person can still join, nearest first, then soonest, then cheapest. Nothing is
    hidden by where the person is: a batch in another state is last, not gone."""
    return await learner.list_public(
        db,
        user,
        state_id=state_id,
        district_id=district_id,
        starts_within=starts_within,
        max_fee=max_fee,
        course_slug=course,
        mode=mode,
        limit=limit,
        offset=offset,
    )


@public_router.get("/{batch_id}", response_model=PublicBatchOut)
async def public_batch(
    batch_id: uuid.UUID,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session),
) -> PublicBatchOut:
    return await learner.get_public(db, user, batch_id)


@me_router.post("", response_model=BatchInterestOut, status_code=status.HTTP_201_CREATED)
async def register_interest(
    payload: BatchInterestIn,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> BatchInterestOut:
    """Tell the centre that runs a batch you want it, sharing your name and contact with it."""
    try:
        batch_id = uuid.UUID(payload.batch_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found") from None
    return await learner.register(db, user, batch_id=batch_id, message=payload.message)


@me_router.get("", response_model=list[BatchInterestOut])
async def my_batch_interests(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> list[BatchInterestOut]:
    return await learner.list_mine(db, user)


@me_router.post("/{interest_id}/withdraw", response_model=BatchInterestOut)
async def withdraw_batch_interest(
    interest_id: uuid.UUID,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> BatchInterestOut:
    """Take it back. The centre keeps the fact and loses your contact details."""
    return await learner.withdraw(db, user, interest_id)
