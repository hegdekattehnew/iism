import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.modules.applications import service
from api.modules.applications.schemas import ApplicationIn, ApplicationOut, SavedJobOut
from api.modules.identity import User, get_current_candidate

# `get_current_candidate`, not `get_current_user`: applying is the job seeker's
# side of the marketplace, and an organisation-only account that never asked
# for a candidate profile should not have one created by pressing Apply.
router = APIRouter(prefix="/me", tags=["applications"])


def _out(application) -> ApplicationOut:  # type: ignore[no-untyped-def]
    return ApplicationOut(
        id=application.id,
        job=application.job,
        status=application.status,
        message=application.message,
        applied_at=application.created_at,
        updated_at=application.updated_at,
    )


@router.post("/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    payload: ApplicationIn,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> ApplicationOut:
    """Apply, and share your name and contact with that employer for that vacancy."""
    return _out(await service.apply(db, user, job_slug=payload.job_slug, message=payload.message))


@router.get("/applications", response_model=list[ApplicationOut])
async def my_applications(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> list[ApplicationOut]:
    return [_out(a) for a in await service.list_applications(db, user)]


@router.post("/applications/{application_id}/withdraw", response_model=ApplicationOut)
async def withdraw_application(
    application_id: uuid.UUID,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> ApplicationOut:
    """Take it back. The employer keeps the fact and loses the contact details."""
    return _out(await service.withdraw(db, user, application_id))


@router.post("/saved-jobs", response_model=SavedJobOut, status_code=status.HTTP_201_CREATED)
async def save_job(
    payload: ApplicationIn,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
) -> SavedJobOut:
    saved = await service.save_job(db, user, payload.job_slug)
    return SavedJobOut(job=saved.job, saved_at=saved.created_at)


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
