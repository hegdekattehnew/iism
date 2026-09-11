import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session

# Candidate routes require a candidate, not merely a signed-in account: an
# organisation-only user used to get a CandidateProfile created on first look.
from api.modules.identity import get_current_candidate
from api.modules.identity.models import User
from api.modules.marketplace import profile_service, schemas
from api.modules.marketplace.models import CandidateProfile

router = APIRouter(prefix="/me", tags=["profile"])


async def _view(
    db: AsyncSession, user: User, profile: CandidateProfile | None = None
) -> schemas.CandidateProfileFull:
    """Serialises a profile, adding the two things that are not columns:
    the user's name (which lives on the identity side) and completeness."""
    if profile is None:
        profile = await profile_service.get_or_create_profile(db, user.id)
    percent, missing = profile_service.compute_completeness(profile, user.full_name)
    out = schemas.CandidateProfileFull.model_validate(profile)
    out.full_name = user.full_name
    out.completeness = schemas.ProfileCompleteness(percent=percent, missing=missing)
    return out


@router.get("/profile", response_model=schemas.CandidateProfileFull)
async def get_profile(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileFull:
    return await _view(db, user)


@router.put("/profile", response_model=schemas.CandidateProfileFull)
async def update_profile(
    payload: schemas.CandidateProfileUpdateFull,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileFull:
    fields = payload.model_dump(exclude_unset=True)

    # full_name belongs to the identity module, not the profile.
    if "full_name" in fields:
        user.full_name = fields.pop("full_name")
        await db.commit()

    profile = (
        await profile_service.update_profile(db, user.id, **fields)
        if fields
        else await profile_service.get_or_create_profile(db, user.id)
    )
    return await _view(db, user, profile)


@router.post("/profile/onboarding/complete", response_model=schemas.CandidateProfileFull)
async def complete_onboarding(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileFull:
    profile = await profile_service.complete_onboarding(db, user.id)
    return await _view(db, user, profile)


# ------------------------------------------------------------------- skills


@router.post("/profile/skills", response_model=schemas.CandidateProfileFull)
async def add_skill(
    payload: schemas.CandidateSkillAdd,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileFull:
    profile = await profile_service.add_skill(db, user.id, payload.skill_slug, payload.proficiency)
    return await _view(db, user, profile)


@router.delete("/profile/skills/{skill_slug}", response_model=schemas.CandidateProfileFull)
async def remove_skill(
    skill_slug: str,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileFull:
    profile = await profile_service.remove_skill(db, user.id, skill_slug)
    return await _view(db, user, profile)


# ------------------------------------------------- repeating profile sections
# Six collections behave identically, so they are routed generically rather
# than as six near-identical blocks.

_PAYLOADS: dict[str, type[BaseModel]] = {
    "experiences": schemas.ExperienceIn,
    "educations": schemas.EducationIn,
    "certifications": schemas.CertificationIn,
    "languages": schemas.LanguageIn,
    "preferred_roles": schemas.PreferredRoleIn,
    "preferred_locations": schemas.PreferredLocationIn,
}


async def _values(db: AsyncSession, collection: str, body: dict) -> dict:
    """Validates against the collection's own schema and maps API fields onto
    columns (certifications take a skill slug, the column is a skill id)."""
    model = _PAYLOADS.get(collection)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown profile section")

    # These routes take an untyped body so one handler can serve six
    # collections, which means FastAPI's automatic 422 does not apply and the
    # validation error has to be translated here.
    try:
        values = model.model_validate(body).model_dump()
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, jsonable_encoder(exc.errors())
        ) from exc
    if collection == "certifications":
        values["skill_id"] = await profile_service.resolve_certification_skill(
            db, values.pop("skill_slug", None)
        )
    return values


@router.post("/profile/{collection}", response_model=schemas.CandidateProfileFull)
async def add_entry(
    collection: str,
    body: dict,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileFull:
    values = await _values(db, collection, body)
    profile = await profile_service.add_child(db, user.id, collection, values)
    return await _view(db, user, profile)


@router.put("/profile/{collection}/{entry_id}", response_model=schemas.CandidateProfileFull)
async def update_entry(
    collection: str,
    entry_id: uuid.UUID,
    body: dict,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileFull:
    values = await _values(db, collection, body)
    profile = await profile_service.update_child(db, user.id, collection, entry_id, values)
    return await _view(db, user, profile)


@router.delete("/profile/{collection}/{entry_id}", response_model=schemas.CandidateProfileFull)
async def remove_entry(
    collection: str,
    entry_id: uuid.UUID,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CandidateProfileFull:
    profile = await profile_service.remove_child(db, user.id, collection, entry_id)
    return await _view(db, user, profile)
