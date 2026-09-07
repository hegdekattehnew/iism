"""Reference data for the forms that need it.

Unauthenticated: the administrative map of India is public information, and a
job-posting form that cannot load its own dropdowns is worse than one anybody
can read.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.modules.geography import schemas, service

router = APIRouter(prefix="/geography", tags=["geography"])


@router.get("/states", response_model=list[schemas.StateOut])
async def list_states(db: AsyncSession = Depends(get_db_session)) -> list[schemas.StateOut]:
    return [schemas.StateOut.model_validate(s) for s in await service.list_states(db)]


@router.get("/districts", response_model=list[schemas.DistrictOut])
async def list_districts(
    state_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.DistrictOut]:
    return [
        schemas.DistrictOut.model_validate(d) for d in await service.list_districts(db, state_id)
    ]
