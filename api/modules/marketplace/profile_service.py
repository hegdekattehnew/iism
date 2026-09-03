"""Candidate profile logic.

Kept in its own module rather than swelling `service.py`: profiles are the
candidate side of the marketplace, jobs and courses the supply side, and Sprint
5's matching reads both.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.modules.marketplace.models import CandidateProfile, CandidateSkill
from api.modules.skills.models import Skill

MAX_SKILLS_PER_PROFILE = 60


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


async def get_or_create_profile(db: AsyncSession, user_id: uuid.UUID) -> CandidateProfile:
    """Profiles are created lazily on first access, so signing in never has to
    decide whether someone is a candidate."""
    profile = await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    if profile is None:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
    return await _load(db, profile.id)


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, **fields: object
) -> CandidateProfile:
    profile = await get_or_create_profile(db, user_id)
    for key, value in fields.items():
        setattr(profile, key, value)
    await db.commit()
    return await _load(db, profile.id)


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
