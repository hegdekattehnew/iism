import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.modules.applications import review_service, service
from api.modules.applications.reputation import poster_reputation_for_job, reviewed_ids
from api.modules.applications.schemas import (
    ApplicationGapOut,
    ApplicationIn,
    ApplicationOut,
    CandidateDashboardOut,
    JobRef,
    PosterRatingOut,
    ReputationOut,
    ReviewIn,
    ReviewOut,
    SavedJobOut,
    TopMatchOut,
)
from api.modules.identity import User, get_current_candidate
from api.modules.matching.schemas import CourseSuggestionOut, MissingSkillOut

# `get_current_candidate`, not `get_current_user`: applying is the job seeker's
# side of the marketplace, and an organisation-only account that never asked
# for a candidate profile should not have one created by pressing Apply.
router = APIRouter(prefix="/me", tags=["applications"])

# Not under `/me`: a poster's rating is public, because a worker choosing whom
# to work for is exactly who it is for. A separate router rather than a field on
# the vacancy's own payload, so `marketplace` does not gain a dependency on this
# module (ADR-014).
public_router = APIRouter(tags=["applications"])


@public_router.get("/jobs/{job_slug}/poster-rating", response_model=PosterRatingOut)
async def poster_rating(
    job_slug: str, db: AsyncSession = Depends(get_db_session)
) -> PosterRatingOut:
    """How workers rated whoever posted this vacancy. Empty, never an error,
    for a vacancy with no ratings or one that is not published."""
    rating = await poster_reputation_for_job(db, job_slug)
    return PosterRatingOut(rating=ReputationOut.model_validate(rating) if rating else None)


def _out(  # type: ignore[no-untyped-def]
    application, titles: dict | None = None, reviewed: bool = False
) -> ApplicationOut:
    """`titles` carries the vacancy's translated title, when there is one.

    Resolved by the caller rather than here: one query for a whole list, not
    one per row (ADR-041). Missed on the first pass, and /hi/applications
    quietly showed English titles until the browser said so.
    """
    job = JobRef.model_validate(application.job)
    if titles:
        job = job.model_copy(update=titles)
    return ApplicationOut(
        id=application.id,
        job=job,
        status=application.status,
        message=application.message,
        applied_at=application.created_at,
        updated_at=application.updated_at,
        reviewed=reviewed,
    )


@router.get("/dashboard", response_model=CandidateDashboardOut)
async def candidate_dashboard(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> CandidateDashboardOut:
    """A candidate's landing numbers (Sprint 39, BL-10.1), and a preview of the
    best-scoring jobs behind `match_count`/`best_score` (Sprint 40).

    Built explicitly rather than `model_validate`d off the dataclass: each
    `TopMatchOut` is assembled from a `ScoredJob`'s two nested objects
    (`job`, `result`), which `from_attributes` cannot flatten on its own.
    """
    data = await service.dashboard(db, user)
    return CandidateDashboardOut(
        match_count=data.match_count,
        best_score=data.best_score,
        applied=data.applied,
        shortlisted=data.shortlisted,
        hired=data.hired,
        profile_completeness=data.profile_completeness,
        rating=ReputationOut.model_validate(data.rating) if data.rating else None,
        top_matches=[
            TopMatchOut(
                job_slug=s.job.slug,
                job_title=s.job.title,
                score=s.result.score,
                coverage=s.result.coverage,
                missing_mandatory=s.result.missing_mandatory,
                capped_by_mandatory=s.result.capped_by_mandatory,
                nsqf_level_min=s.job.nsqf_level_min,
                level_shortfall=s.result.level_shortfall,
            )
            for s in data.top_matches
        ],
    )


@router.post("/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    payload: ApplicationIn,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> ApplicationOut:
    """Apply, and share your name and contact with that employer for that vacancy."""
    application = await service.apply(db, user, job_slug=payload.job_slug, message=payload.message)
    overrides = await overrides_for(db, "job", [application.job], ("title",), locale)
    return _out(application, overrides.get(application.job_id))


@router.get("/applications", response_model=list[ApplicationOut])
async def my_applications(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> list[ApplicationOut]:
    applications = await service.list_applications(db, user)
    overrides = await overrides_for(db, "job", [a.job for a in applications], ("title",), locale)
    rated = await reviewed_ids(db, [a.id for a in applications], "poster")
    return [_out(a, overrides.get(a.job_id), a.id in rated) for a in applications]


@router.post("/applications/{application_id}/withdraw", response_model=ApplicationOut)
async def withdraw_application(
    application_id: uuid.UUID,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> ApplicationOut:
    """Take it back. The employer keeps the fact and loses the contact details."""
    application = await service.withdraw(db, user, application_id)
    overrides = await overrides_for(db, "job", [application.job], ("title",), locale)
    rated = await reviewed_ids(db, [application.id], "poster")
    return _out(application, overrides.get(application.job_id), application.id in rated)


@router.get("/applications/{application_id}/gap", response_model=ApplicationGapOut)
async def application_gap(
    application_id: uuid.UUID,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> ApplicationGapOut:
    """Why not me: the standards this application was missing, and the courses
    that teach them. Computed now, from the candidate's skills as they stand."""
    gap = await service.application_gap(db, user, application_id)
    overrides = await overrides_for(db, "job", [gap.application.job], ("title",), locale)
    job = JobRef.model_validate(gap.application.job).model_copy(
        update=overrides.get(gap.application.job_id, {})
    )
    result = gap.result
    return ApplicationGapOut(
        application_id=gap.application.id,
        job=job,
        status=gap.application.status,
        score=result.score,
        coverage=round(result.coverage, 4),
        missing=[MissingSkillOut.from_missing(m) for m in result.missing],
        missing_mandatory=result.missing_mandatory,
        level_shortfall=float(result.level_shortfall)
        if result.level_shortfall is not None
        else None,
        capped_by_mandatory=result.capped_by_mandatory,
        courses=[CourseSuggestionOut.from_suggestion(c) for c in gap.courses],
    )


@router.post(
    "/applications/{application_id}/review",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
async def review_poster(
    application_id: uuid.UUID,
    payload: ReviewIn,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> ReviewOut:
    """Rate the poster of a completed gig engagement (Sprint 37, Epic B8)."""
    review = await review_service.submit_poster_review(
        db, user, application_id, rating=payload.rating, comment=payload.comment
    )
    return ReviewOut.model_validate(review)


@router.post("/saved-jobs", response_model=SavedJobOut, status_code=status.HTTP_201_CREATED)
async def save_job(
    payload: ApplicationIn,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> SavedJobOut:
    saved = await service.save_job(db, user, payload.job_slug)
    overrides = await overrides_for(db, "job", [saved.job], ("title",), locale)
    job = JobRef.model_validate(saved.job).model_copy(update=overrides.get(saved.job_id, {}))
    return SavedJobOut(job=job, saved_at=saved.created_at)


@router.get("/saved-jobs", response_model=list[SavedJobOut])
async def my_saved_jobs(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> list[SavedJobOut]:
    return [
        SavedJobOut(job=s.job, saved_at=s.created_at) for s in await service.list_saved(db, user)
    ]


@router.delete("/saved-jobs/{job_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_job(
    job_slug: str,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    await service.unsave_job(db, user, job_slug)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
