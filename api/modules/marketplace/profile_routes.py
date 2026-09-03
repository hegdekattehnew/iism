from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity.models import User
from api.modules.marketplace import profile_service, schemas

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("/profile", response_model=schemas.CandidateProfileOut)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileOut:
    profile = await profile_service.get_or_create_profile(db, user.id)
    return schemas.CandidateProfileOut.model_validate(profile)


@router.put("/profile", response_model=schemas.CandidateProfileOut)
async def update_profile(
    payload: schemas.CandidateProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileOut:
    profile = await profile_service.update_profile(
        db, user.id, **payload.model_dump(exclude_unset=False)
    )
    return schemas.CandidateProfileOut.model_validate(profile)


@router.post("/profile/skills", response_model=schemas.CandidateProfileOut)
async def add_skill(
    payload: schemas.CandidateSkillAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileOut:
    profile = await profile_service.add_skill(db, user.id, payload.skill_slug, payload.proficiency)
    return schemas.CandidateProfileOut.model_validate(profile)


@router.delete("/profile/skills/{skill_slug}", response_model=schemas.CandidateProfileOut)
async def remove_skill(
    skill_slug: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileOut:
    profile = await profile_service.remove_skill(db, user.id, skill_slug)
    return schemas.CandidateProfileOut.model_validate(profile)
