"""Candidate profile logic.

Kept in its own module rather than swelling `service.py`: profiles are the
candidate side of the marketplace, jobs and courses the supply side, and Sprint
5's matching reads both.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.modules.marketplace.models import (
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidatePreferredLocation,
    CandidatePreferredRole,
    CandidateProfile,
    CandidateSkill,
)
from api.modules.skills.models import Skill

MAX_SKILLS_PER_PROFILE = 60
MAX_ROWS_PER_COLLECTION = 30

# Every child collection of the profile, by the name the API exposes.
#
# Typed as Any because the model is resolved by name at runtime: the six
# classes share the shape the generic CRUD needs (id, profile_id) but have no
# common base declaring it, so a narrower annotation would be a fiction.
ChildModel = type[Any]

CHILD_MODELS: dict[str, ChildModel] = {
    "experiences": CandidateExperience,
    "educations": CandidateEducation,
    "certifications": CandidateCertification,
    "languages": CandidateLanguage,
    "preferred_roles": CandidatePreferredRole,
    "preferred_locations": CandidatePreferredLocation,
}


async def _load(db: AsyncSession, profile_id: uuid.UUID) -> CandidateProfile:
    """Re-read with the nested relationship eagerly loaded.

    Two traps are being avoided here, both silent:

    * `db.refresh()` does not cascade eager loading to `skills -> skill`, so
      serialising the result lazy-loads and fails outside the greenlet.
    * Without `populate_existing`, the instance already in the session's
      identity map is returned as-is and its stale (often empty) `skills`
      collection wins — the query succeeds and simply returns the wrong answer.
    """
    profile = await db.scalar(
        select(CandidateProfile)
        .where(CandidateProfile.id == profile_id)
        .options(selectinload(CandidateProfile.skills).selectinload(CandidateSkill.skill))
        .execution_options(populate_existing=True)
    )
    assert profile is not None  # noqa: S101 - just committed it
    return profile


async def ensure_profile(db: AsyncSession, user_id: uuid.UUID) -> CandidateProfile:
    """The profile row, created if this is the first time anyone asked for it.

    Profiles are lazy so that signing in never has to decide whether someone is
    a candidate. The single place that creation happens.

    **Leaves no uncommitted work.** It either finds a row and writes nothing, or
    creates one and commits — which is what lets a handler call `record()`
    afterwards, since `record()` commits and would otherwise sweep a
    half-finished write in with it (see `api/modules/analytics/service.py`).

    Returns the bare row. Callers wanting the profile *and* its skills want
    `get_or_create_profile` instead.
    """
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    if profile is None:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
    return profile


async def get_or_create_profile(db: AsyncSession, user_id: uuid.UUID) -> CandidateProfile:
    """The profile with its skills eagerly loaded, ready to serialise."""
    profile = await ensure_profile(db, user_id)
    return await _load(db, profile.id)


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, **fields: object
) -> CandidateProfile:
    """Applies only the keys supplied.

    Sections save independently, so a payload carrying three fields must not
    null out the fifteen it does not mention.
    """
    profile = await get_or_create_profile(db, user_id)
    for key, value in fields.items():
        setattr(profile, key, value)
    await db.commit()
    return await _load(db, profile.id)


async def resolve_certification_skill(db: AsyncSession, skill_slug: str | None) -> uuid.UUID | None:
    if not skill_slug:
        return None
    skill = await db.scalar(select(Skill).where(Skill.slug == skill_slug))
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    return skill.id


async def add_skill(
    db: AsyncSession,
    user_id: uuid.UUID,
    skill_slug: str,
    proficiency: int,
) -> CandidateProfile:
    profile = await get_or_create_profile(db, user_id)

    skill = await db.scalar(select(Skill).where(Skill.slug == skill_slug))
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")

    existing = await db.scalar(
        select(CandidateSkill).where(
            CandidateSkill.profile_id == profile.id,
            CandidateSkill.skill_id == skill.id,
        )
    )
    if existing is not None:
        # Re-adding updates the proficiency rather than erroring; that is what
        # the user means, and it keeps the UI from needing a separate edit path.
        existing.proficiency = proficiency
    else:
        if len(profile.skills) >= MAX_SKILLS_PER_PROFILE:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"A profile may list at most {MAX_SKILLS_PER_PROFILE} skills",
            )
        db.add(
            CandidateSkill(
                profile_id=profile.id,
                skill_id=skill.id,
                proficiency=proficiency,
                # Anything a user types about themselves is self-declared. Only
                # an assessment or certificate may set a stronger source.
                source="self_declared",
            )
        )

    await db.commit()
    return await _load(db, profile.id)


async def remove_skill(db: AsyncSession, user_id: uuid.UUID, skill_slug: str) -> CandidateProfile:
    profile = await get_or_create_profile(db, user_id)
    skill = await db.scalar(select(Skill).where(Skill.slug == skill_slug))
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")

    await db.execute(
        delete(CandidateSkill).where(
            CandidateSkill.profile_id == profile.id,
            CandidateSkill.skill_id == skill.id,
        )
    )
    await db.commit()
    return await _load(db, profile.id)


# ------------------------------------------------------------- completeness

# Weighted so the meter reflects usefulness to matching, not field count.
# Preferred roles score highest because without a target there is nothing to
# compute a gap against.
_COMPLETENESS_RULES: list[tuple[str, int]] = [
    ("full_name", 10),
    ("headline", 5),
    ("location", 10),
    ("skills", 25),
    ("preferred_roles", 20),
    ("experiences", 15),
    ("educations", 10),
    ("languages", 5),
]


def compute_completeness(profile: CandidateProfile, full_name: str | None) -> tuple[int, list[str]]:
    have = {
        "full_name": bool(full_name),
        "headline": bool(profile.headline),
        "location": bool(profile.location_state),
        "skills": len(profile.skills) > 0,
        "preferred_roles": len(profile.preferred_roles) > 0,
        "experiences": len(profile.experiences) > 0,
        "educations": len(profile.educations) > 0,
        "languages": len(profile.languages) > 0,
    }
    percent = sum(weight for key, weight in _COMPLETENESS_RULES if have[key])
    missing = [key for key, _ in _COMPLETENESS_RULES if not have[key]]
    return percent, missing


# --------------------------------------------------- generic child CRUD
# All six collections behave identically, so they share one implementation
# rather than six near-copies that drift apart.


def _model_for(collection: str) -> ChildModel:
    model = CHILD_MODELS.get(collection)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown profile section")
    return model


async def add_child(
    db: AsyncSession, user_id: uuid.UUID, collection: str, values: dict
) -> CandidateProfile:
    model = _model_for(collection)
    profile = await get_or_create_profile(db, user_id)

    existing = await db.scalar(
        select(func.count()).select_from(model).where(model.profile_id == profile.id)
    )
    if (existing or 0) >= MAX_ROWS_PER_COLLECTION:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A profile may hold at most {MAX_ROWS_PER_COLLECTION} entries here",
        )

    db.add(model(profile_id=profile.id, **values))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # Unique constraints on languages, preferred roles and locations.
        raise HTTPException(status.HTTP_409_CONFLICT, "That entry already exists") from exc
    return await _load(db, profile.id)


async def update_child(
    db: AsyncSession,
    user_id: uuid.UUID,
    collection: str,
    entry_id: uuid.UUID,
    values: dict,
) -> CandidateProfile:
    model = _model_for(collection)
    profile = await get_or_create_profile(db, user_id)

    # Scoped to this profile: without the profile_id predicate a candidate could
    # edit another candidate's entry by guessing an id.
    entry = await db.scalar(
        select(model).where(model.id == entry_id, model.profile_id == profile.id)
    )
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")

    for key, value in values.items():
        setattr(entry, key, value)
    await db.commit()
    return await _load(db, profile.id)


async def remove_child(
    db: AsyncSession, user_id: uuid.UUID, collection: str, entry_id: uuid.UUID
) -> CandidateProfile:
    model = _model_for(collection)
    profile = await get_or_create_profile(db, user_id)
    result = await db.execute(
        delete(model).where(model.id == entry_id, model.profile_id == profile.id)
    )
    # rowcount tells us whether the entry existed *and* belonged to this
    # profile, which is what distinguishes 404 from a silent no-op.
    if cast("CursorResult[Any]", result).rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    await db.commit()
    return await _load(db, profile.id)


async def complete_onboarding(db: AsyncSession, user_id: uuid.UUID) -> CandidateProfile:
    """Marks the guided wizard finished so the sectioned editor is shown next."""
    profile = await get_or_create_profile(db, user_id)
    profile.onboarding_completed_at = datetime.now(UTC)
    await db.commit()
    return await _load(db, profile.id)
