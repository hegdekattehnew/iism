"""`GET /me/careers` -- the roles that build on a candidate's own."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.modules.careers import schemas, service
from api.modules.identity import get_current_candidate
from api.modules.identity.models import User
from api.modules.marketplace import ensure_profile

router = APIRouter(prefix="/me/careers", tags=["careers"])


@router.get("", response_model=schemas.CareerLadderOut)
async def career_ladder(
    role: str | None = Query(
        None,
        max_length=300,
        description=(
            "The slug of the role to start from. Omit it and the API guesses once, "
            "from the profile, and says so in `anchor_source`."
        ),
    ),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_candidate),
) -> schemas.CareerLadderOut:
    # Gated by `get_current_candidate`, like `/me/matches`: an organisation-only
    # account never gets a candidate profile created by looking at this.
    # `ensure_profile` commits when it creates and writes nothing otherwise, so
    # the `record()` inside the service has none of our uncommitted work to sweep.
    profile = await ensure_profile(db, user.id)
    return schemas.CareerLadderOut.from_ladder(
        await service.career_ladder(db, user.id, profile.id, role)
    )
