import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.modules.applications import review_service, service
from api.modules.applications.schemas import (
    ApplicationIn,
    ApplicationOut,
    CandidateDashboardOut,
    JobRef,
    ReviewIn,
    ReviewOut,
    SavedJobOut,
)
from api.modules.identity import User, get_current_candidate

# `get_current_candidate`, not `get_current_user`: applying is the job seeker's
# side of the marketplace, and an organisation-only account that never asked
# for a candidate profile should not have one created by pressing Apply.
router = APIRouter(prefix="/me", tags=["applications"])


def _out(application, titles: dict | None = None) -> ApplicationOut:  # type: ignore[no-untyped-def]
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
    )


@router.get("/dashboard", response_model=CandidateDashboardOut)
async def candidate_dashboard(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> CandidateDashboardOut:
    """A candidate's landing numbers (Sprint 39, BL-10.1)."""
    return CandidateDashboardOut.model_validate(await service.dashboard(db, user))


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
    return [_out(a, overrides.get(a.job_id)) for a in applications]


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
    return _out(application, overrides.get(application.job_id))


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
