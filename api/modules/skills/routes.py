from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.modules.skills import schemas, service

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/count", response_model=schemas.SkillCount)
async def skill_count(db: AsyncSession = Depends(get_db_session)) -> schemas.SkillCount:
    return schemas.SkillCount(count=await service.count_skills(db))


@router.get("/facets", response_model=schemas.SkillFacets)
async def skill_facets(db: AsyncSession = Depends(get_db_session)) -> schemas.SkillFacets:
    levels, types, unlevelled, total = await service.skill_facets(db)
    return schemas.SkillFacets(
        total=total,
        levels=[schemas.LevelFacet(level=lv, count=c) for lv, c in levels],
        types=[schemas.TypeFacet(skill_type=ty, count=c) for ty, c in types],
        unlevelled=unlevelled,
    )


@router.get("/search", response_model=list[schemas.SkillSearchHit])
async def search_skills(
    q: str = Query(min_length=1, max_length=120, description="Free text, any script"),
    limit: int = Query(20, ge=1, le=service.MAX_SEARCH_RESULTS),
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.SkillSearchHit]:
    hits = await service.search_skills(db, q, limit=limit)
    contexts = await service.contexts_for(db, [h.skill.id for h in hits])
    return [
        schemas.SkillSearchHit(
            **schemas.SkillOut.model_validate(h.skill).model_dump(exclude={"context"}),
            matched_on=h.matched_on,
            match_kind=h.match_kind,
            context=_context(contexts.get(h.skill.id)),
        )
        for h in hits
    ]


def _context(found: service.SkillContext | None) -> schemas.SkillContextOut | None:
    return schemas.SkillContextOut(**vars(found)) if found is not None else None


@router.get("", response_model=schemas.SkillPage)
async def list_skills(
    skill_type: schemas.SkillType | None = Query(None),
    nsqf_level: float | None = Query(None, ge=1, le=10),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> schemas.SkillPage:
    items, total = await service.list_skills(
        db, skill_type=skill_type, nsqf_level=nsqf_level, limit=limit, offset=offset
    )
    # One query for the page, applied at serialisation (ADR-041).
    overrides = await overrides_for(db, "skill", items, ("name", "description"), locale)
    contexts = await service.contexts_for(db, [s.id for s in items])
    return schemas.SkillPage(
        items=[
            schemas.SkillOut.model_validate(s).model_copy(
                update={**overrides.get(s.id, {}), "context": _context(contexts.get(s.id))}
            )
            for s in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{slug}/requirements", response_model=schemas.SkillRequirements)
async def skill_requirements(
    slug: str, db: AsyncSession = Depends(get_db_session)
) -> schemas.SkillRequirements:
    skill = await service.get_skill_by_slug(db, slug)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    bundle = await service.requirements_for_skill(db, skill.id)
    return schemas.SkillRequirements(
        elements=[
            schemas.PerformanceElementOut(
                name=element.name,
                total_marks=element.total_marks,
                criteria=[schemas.CriterionOut.model_validate(c) for c in criteria],
            )
            for element, criteria in bundle.elements
        ],
        criteria_count=sum(len(c) for _, c in bundle.elements),
        knowledge=bundle.knowledge,
        generic_skills=bundle.generic_skills,
    )


@router.get("/{slug}/qualifications", response_model=schemas.SkillQualifications)
async def skill_qualifications(
    slug: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.SkillQualifications:
    skill = await service.get_skill_by_slug(db, slug)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    items, total = await service.qualifications_for_skill(db, skill.id, limit=limit)
    return schemas.SkillQualifications(
        items=[schemas.QualificationRefOut.model_validate(q) for q in items],
        total=total,
    )


# Declared last: a literal path like /skills/search must not be captured by this.
@router.get("/{slug}", response_model=schemas.SkillDetail)
async def get_skill(
    slug: str,
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> schemas.SkillDetail:
    skill = await service.get_skill_by_slug(db, slug)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    overrides = await overrides_for(db, "skill", [skill], ("name", "description"), locale)
    return schemas.SkillDetail.model_validate(skill).model_copy(update=overrides.get(skill.id, {}))
