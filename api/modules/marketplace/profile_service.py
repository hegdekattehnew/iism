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

from api.modules.geography import resolve_location
from api.modules.identity.models import User
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


async def update_profile(db: AsyncSession, user: User, **fields: object) -> CandidateProfile:
    """Applies only the keys supplied.

    Sections save independently, so a payload carrying three fields must not
    null out the fifteen it does not mention.

    **Takes the `User`, not a user id, because one field on this form is not a
    profile field.** `full_name` belongs to the identity side; the route used to
    pop it off the payload, set it, and commit -- so saving a name and saving a
    headline were two transactions, and the first could land while the second
    failed. One screen, one save, one commit.
    """
    if "full_name" in fields:
        user.full_name = cast(str | None, fields.pop("full_name"))
    profile = await get_or_create_profile(db, user.id)
    for key, value in fields.items():
        setattr(profile, key, value)
    if _LOCATION_FIELDS & fields.keys():
        # Resolved on write, as a job's is (`publishing.create_job`). Before
        # Sprint 23 this was a bare setattr and the only writer of `state_id` was
        # the NSQF importer's backfill -- so every profile written through the
        # API had a NULL state and was invisible to anything location-aware,
        # while every *seeded* profile looked fine because the import happened
        # to run after it. Sprint 15's bug, one table over.
        #
        # Both halves from the row, not the payload: a request that changes only
        # the district must still resolve against the state already held.
        location = await resolve_location(db, profile.location_state, profile.location_district)
        profile.state_id, profile.district_id = location.state_id, location.district_id
    await db.commit()
    return await _load(db, profile.id)


_LOCATION_FIELDS = {"location_state", "location_district"}


async def resolve_preferred_location(db: AsyncSession, values: dict) -> dict:
    """Adds the resolved ids to a preferred-location payload.

    The free text is kept whatever happens: the ids sit *beside* it, because an
    unresolvable place is still a place somebody said they would work.
    """
    location = await resolve_location(db, values.get("state"), values.get("district"))
    return {**values, "state_id": location.state_id, "district_id": location.district_id}


async def resolve_certification_skill(db: AsyncSession, skill_slug: str | None) -> uuid.UUID | None:
    if not skill_slug:
        return None
    skill = await db.scalar(select(Skill).where(Skill.slug == skill_slug))
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    return skill.id


async def _write_skills(
    db: AsyncSession, profile: CandidateProfile, items: list[tuple[str, int]]
) -> tuple[int, int]:
    """The one place a candidate's own claim becomes a `CandidateSkill` row.

    Both the single add and the bulk add come through here, and nothing else in
    the request path constructs one. That is what keeps `source` honest: a
    second construction site is how a suggested standard would one day be
    written as `inferred` -- which scores *above* `self_declared` (0.7 against
    0.6), and would let the easy path outrank a candidate who typed the same
    standards by hand. Suggestion changes how a standard is found, never how
    well it is evidenced.

    All or nothing. Every slug is resolved and the cap checked **before**
    anything is written: a batch of eight that lands three, with nothing on
    screen saying which five were dropped, is worse than a refusal. Does not
    commit; returns `(added, updated)`.
    """
    # Last proficiency wins for a slug listed twice.
    wanted = dict(items)
    skills = {
        skill.slug: skill
        for skill in await db.scalars(select(Skill).where(Skill.slug.in_(list(wanted))))
    }
    unknown = sorted(set(wanted) - skills.keys())
    if unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Skill not found: {', '.join(unknown)}")

    held = {
        row.skill_id: row
        for row in await db.scalars(
            select(CandidateSkill).where(
                CandidateSkill.profile_id == profile.id,
                CandidateSkill.skill_id.in_([s.id for s in skills.values()]),
            )
        )
    }
    # Only new standards count toward the cap; re-adding one is an edit.
    new = [slug for slug in wanted if skills[slug].id not in held]
    current = (
        await db.scalar(
            select(func.count())
            .select_from(CandidateSkill)
            .where(CandidateSkill.profile_id == profile.id)
        )
    ) or 0
    if current + len(new) > MAX_SKILLS_PER_PROFILE:
        room = max(MAX_SKILLS_PER_PROFILE - current, 0)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A profile may list at most {MAX_SKILLS_PER_PROFILE} skills; "
            f"there is room for {room} more",
        )

    for slug, proficiency in wanted.items():
        existing = held.get(skills[slug].id)
        if existing is not None:
            # Re-adding updates the proficiency rather than erroring; that is
            # what the user means, and it keeps the UI from needing a separate
            # edit path.
            existing.proficiency = proficiency
        else:
            db.add(
                CandidateSkill(
                    profile_id=profile.id,
                    skill_id=skills[slug].id,
                    proficiency=proficiency,
                    # Anything a user says about themselves is self-declared --
                    # typed or ticked. Only an assessment or certificate may set
                    # a stronger source.
                    source="self_declared",
                )
            )
    return len(new), len(wanted) - len(new)


async def add_skill(
    db: AsyncSession,
    user_id: uuid.UUID,
    skill_slug: str,
    proficiency: int,
) -> CandidateProfile:
    profile = await get_or_create_profile(db, user_id)
    await _write_skills(db, profile, [(skill_slug, proficiency)])
    await db.commit()
    return await _load(db, profile.id)


async def add_skills_bulk(
    db: AsyncSession,
    user_id: uuid.UUID,
    items: list[tuple[str, int]],
    preferred_role_title: str | None = None,
) -> tuple[CandidateProfile, int, int]:
    """Several standards in one request, and optionally the role they came from.

    Ticking eight suggested standards is one decision, so it is one request and
    one commit. The role is recorded as a preferred role because the candidate
    has just told us their target -- the fact the completeness meter weights
    highest -- but it is secondary: a duplicate or a full collection is skipped,
    never allowed to fail the skills it arrived with. Returns the profile and
    `(added, updated)`.
    """
    profile = await get_or_create_profile(db, user_id)
    added, updated = await _write_skills(db, profile, items)

    title = (preferred_role_title or "").strip()
    if title:
        roles = list(
            await db.scalars(
                select(CandidatePreferredRole).where(
                    CandidatePreferredRole.profile_id == profile.id
                )
            )
        )
        # Check, then insert -- never lean on the unique constraint, whose
        # IntegrityError would roll back the skills written above.
        already = any(r.title.strip().lower() == title.lower() for r in roles)
        if not already and len(roles) < MAX_ROWS_PER_COLLECTION:
            db.add(CandidatePreferredRole(profile_id=profile.id, title=title))

    await db.commit()

    # Measured here, after the commit, rather than in the route. `record()`
    # commits, so calling it while these skills were still uncommitted would
    # commit them as a side effect -- and a failure inside it would roll them
    # back and return silently, because `record()` never raises.
    #
    # Counts only: which standards somebody holds is a description of them, and
    # `analytics_events` describes nobody. `from_role` is the whole hypothesis
    # Sprint 23 set out to measure -- that naming a role beats searching the
    # standards -- so it is a fact about this write, not a shape of a response.
    #
    # Imported inside the function: `analytics` loads its routes, which load
    # `marketplace.models`, which runs this package's `__init__`.
    from api.modules.analytics import record

    await record(
        db,
        "skills_bulk_added",
        user_id=user_id,
        payload={
            "added": added,
            "updated": updated,
            # bool(), not `is not None`: an empty title is no title.
            "from_role": bool(preferred_role_title),
        },
    )
    return await _load(db, profile.id), added, updated


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
