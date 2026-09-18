"""Role search: name your job, and be offered the standards behind it.

Its own router, on its own prefix, because `/skills/roles` would be captured by
`/skills/{slug}` -- and because a role is a different thing from a standard: it
is the candidate's vocabulary, where the standard is the corpus's.

Public, like the rest of the taxonomy. The national qualification structure is
published information, and a sign-up wizard cannot demand an account before it
helps someone describe what they do.
"""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.core.security import get_optional_user
from api.modules.skills import schemas, service

if TYPE_CHECKING:
    from api.modules.identity.models import User

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/search", response_model=list[schemas.RoleHit])
async def search_roles(
    q: str = Query(min_length=1, max_length=120, description="A job title, any script"),
    limit: int = Query(20, ge=1, le=service.MAX_ROLE_RESULTS),
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.RoleHit]:
    hits = await service.search_roles(db, q, limit=limit)
    return [schemas.RoleHit.model_validate(h, from_attributes=True) for h in hits]


# Declared after `/search` so the literal path is never read as a slug.
@router.get("/{slug}/standards", response_model=schemas.RoleStandards)
async def role_standards(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
    user: "User | None" = Depends(get_optional_user),
) -> schemas.RoleStandards:
    # Imported here, not at the top. `analytics` loads its routes, which load
    # `marketplace.models`, which load `skills` -- so a module-level import
    # would make `skills` and `analytics` each wait on the other at boot. Same
    # fix `matching` uses for `applications`, for the same reason.
    from api.modules.analytics import record

    found = await service.standards_for_role(db, slug)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Qualification not found")

    skills = [s.skill for s in found.standards]
    overrides = await overrides_for(db, "skill", skills, ("name", "description"), locale)
    out = schemas.RoleStandards(
        slug=found.qp.slug,
        job_role=found.qp.job_role,
        qp_code=found.qp.qp_code,
        qp_name=found.qp.name,
        nsqf_level=float(found.qp.nsqf_level) if found.qp.nsqf_level is not None else None,
        sector_name=found.sector_name,
        variants=found.variants,
        standards=[
            schemas.RoleStandardOut(
                **schemas.SkillOut.model_validate(s.skill)
                .model_copy(update=overrides.get(s.skill.id, {}))
                .model_dump(),
                requirement=s.requirement,
                group_name=s.group_name,
                weightage=s.weightage,
            )
            for s in found.standards
        ],
    )
    # Counts only. Which role someone looked at is about the role; the event
    # carries `user_id` and nothing else that identifies them. `record()`
    # commits, and this handler has no other uncommitted work.
    await record(
        db,
        "role_suggested",
        user_id=user.id if user is not None else None,
        subject_type="qualification",
        subject_id=found.qp.id,
        payload={"standards": len(found.standards), "variants": found.variants},
    )
    return out
