from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.modules.marketplace import schemas, service
from api.modules.skills import get_skill_by_slug

jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])
courses_router = APIRouter(prefix="/courses", tags=["courses"])
marketplace_router = APIRouter(tags=["marketplace"])


@marketplace_router.get("/marketplace/counts", response_model=schemas.MarketplaceCounts)
async def marketplace_counts(
    db: AsyncSession = Depends(get_db_session),
) -> schemas.MarketplaceCounts:
    """Backs the homepage browse panels in one round trip."""
    return schemas.MarketplaceCounts(
        jobs=await service.count_jobs(db), courses=await service.count_courses(db)
    )


# ----------------------------------------------------------------------- jobs


@jobs_router.get("", response_model=schemas.JobPage)
async def list_jobs(
    q: str | None = Query(None, max_length=120),
    skill: str | None = Query(None, description="Filter by skill slug"),
    location_state: str | None = Query(None),
    employment_type: schemas.EmploymentType | None = Query(None),
    nsqf_level_max: int | None = Query(None, ge=1, le=10),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.JobPage:
    items, total = await service.list_jobs(
        db,
        q=q,
        skill_slug=skill,
        location_state=location_state,
        employment_type=employment_type,
        nsqf_level_max=nsqf_level_max,
        limit=limit,
        offset=offset,
    )
    return schemas.JobPage(
        items=[schemas.JobOut.model_validate(j) for j in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@jobs_router.get("/{slug}", response_model=schemas.JobDetail)
async def get_job(slug: str, db: AsyncSession = Depends(get_db_session)) -> schemas.JobDetail:
    job = await service.get_job_by_slug(db, slug)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return schemas.JobDetail.model_validate(job)


# -------------------------------------------------------------------- courses


@courses_router.get("", response_model=schemas.CoursePage)
async def list_courses(
    q: str | None = Query(None, max_length=120),
    skill: str | None = Query(None, description="Filter by skill slug"),
    mode: schemas.CourseMode | None = Query(None),
    language: schemas.CourseLanguage | None = Query(None),
    max_fee_inr: int | None = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CoursePage:
    items, total = await service.list_courses(
        db,
        q=q,
        skill_slug=skill,
        mode=mode,
        language=language,
        max_fee_inr=max_fee_inr,
        limit=limit,
        offset=offset,
    )
    return schemas.CoursePage(
        items=[schemas.CourseOut.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@courses_router.get("/{slug}", response_model=schemas.CourseDetail)
async def get_course(slug: str, db: AsyncSession = Depends(get_db_session)) -> schemas.CourseDetail:
    course = await service.get_course_by_slug(db, slug)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return schemas.CourseDetail.model_validate(course)


# ------------------------------------------------------- skill ↔ marketplace
# These edges live here, not in the skills module: marketplace already depends
# on skills, and the reverse import would be a cycle.


@marketplace_router.get("/skills/{slug}/jobs", response_model=list[schemas.JobOut], tags=["skills"])
async def jobs_for_skill(
    slug: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.JobOut]:
    skill = await get_skill_by_slug(db, slug)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    jobs = await service.jobs_requiring_skill(db, skill.id, limit=limit)
    return [schemas.JobOut.model_validate(j) for j in jobs]


@marketplace_router.get(
    "/skills/{slug}/courses", response_model=list[schemas.CourseOut], tags=["skills"]
)
async def courses_for_skill(
    slug: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.CourseOut]:
    skill = await get_skill_by_slug(db, slug)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    courses = await service.courses_teaching_skill(db, skill.id, limit=limit)
    return [schemas.CourseOut.model_validate(c) for c in courses]
