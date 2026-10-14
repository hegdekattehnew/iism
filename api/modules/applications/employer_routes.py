import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.modules.applications import employer_service, review_service
from api.modules.applications.reputation import reviewed_ids
from api.modules.applications.schemas import (
    ApplicantOut,
    ApplicantPage,
    EmployerDashboardOut,
    JobRef,
    NotesIn,
    ReputationOut,
    ReviewIn,
    ReviewOut,
    StatusIn,
)
from api.modules.applications.serialisers import applicant_out
from api.modules.matching.schemas import JobPoolOut, JobSummary

# Employers only, and only their own vacancies. `require` asks both questions
# in one declaration -- a guard a handler must remember to call is one that
# eventually is not called (Sprint 15).
router = APIRouter(prefix="/org/{org_slug}/jobs/{job_slug}/applications", tags=["applications"])
CanShortlist = Depends(require(Permission.CANDIDATE_SHORTLIST, "job"))

# A separate router, not a route on the one above: that one requires a
# `job_slug` in its own prefix, and a dashboard is aggregated across every job
# a tenant owns, not scoped to one. Bare `/org/{org_slug}` -- checked against
# every other router sharing that prefix before picking `/dashboard`, since
# `course_publishing_routes.py`'s `/org/{org_slug}/courses/{slug}` already
# proved a dynamic single-segment route elsewhere in `main.py` can intercept a
# literal one here regardless of registration order within this file alone.
dashboard_router = APIRouter(prefix="/org/{org_slug}", tags=["applications"])


@dashboard_router.get("/dashboard", response_model=EmployerDashboardOut)
async def employer_dashboard(
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> EmployerDashboardOut:
    """An employer's landing numbers, and the per-job pool behind them
    (Sprint 39, BL-10.2; the `jobs` breakdown is Sprint 40).

    Built explicitly rather than `model_validate`d straight off the
    dataclass: `JobPoolOut` carries no `from_attributes` config, matching how
    the employer console's own `_overview()` builds it in
    `matching/employer_routes.py`.
    """
    data = await employer_service.dashboard(db, context.tenant.id)
    return EmployerDashboardOut(
        posted_jobs=data.posted_jobs,
        open_jobs=data.open_jobs,
        applied=data.applied,
        shortlisted=data.shortlisted,
        hired=data.hired,
        rating=ReputationOut.model_validate(data.rating) if data.rating else None,
        jobs=[
            JobPoolOut(
                job=JobSummary.model_validate(p.job),
                pool=p.pool,
                ready=p.ready,
                nearly=p.nearly,
                applications=p.applications,
                new_applications=p.new_applications,
            )
            for p in data.jobs
        ],
    )


@router.get("", response_model=ApplicantPage)
async def list_applicants(
    job_slug: str,
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> ApplicantPage:
    """Who applied, ranked, with contact details while each application is live."""
    job, rows = await employer_service.inbox(db, context.tenant.id, job_slug)
    overrides = await overrides_for(db, "job", [job], ("title",), locale)
    rated = await reviewed_ids(db, [row[0].id for row in rows], "worker")
    items = [applicant_out(*row, reviewed=row[0].id in rated) for row in rows]
    return ApplicantPage(
        job=JobRef.model_validate(job).model_copy(update=overrides.get(job.id, {})),
        items=items,
        total=len(items),
    )


@router.get(
    "/export",
    response_class=Response,
    responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}},
)
async def export_applicants(
    job_slug: str,
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """This vacancy's applicants as a CSV, built from the same function as the list: a withdrawn
    applicant's name, phone, email and covering note are blank. Recorded with a count."""
    text, _count = await employer_service.export_applicants(db, context.tenant.id, job_slug)
    return Response(
        text,
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": f'attachment; filename="applicants-{job_slug}.csv"'},
    )


@router.patch("/{application_id}", response_model=ApplicantOut)
async def set_application_status(
    job_slug: str,
    application_id: uuid.UUID,
    payload: StatusIn,
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> ApplicantOut:
    """Shortlist, reject, hire -- or, for a gig, complete/no-show. A withdrawn
    application cannot be moved."""
    row = await employer_service.set_status_and_reload(
        db, context.tenant.id, job_slug, application_id, payload.status, payload.message
    )
    rated = await reviewed_ids(db, [row[0].id], "worker")
    return applicant_out(*row, reviewed=row[0].id in rated)


@router.post(
    "/{application_id}/review", response_model=ReviewOut, status_code=status.HTTP_201_CREATED
)
async def review_worker(
    job_slug: str,
    application_id: uuid.UUID,
    payload: ReviewIn,
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> ReviewOut:
    """Rate the worker of a completed gig engagement (Sprint 37, Epic B8)."""
    review = await review_service.submit_worker_review(
        db,
        context.tenant.id,
        job_slug,
        application_id,
        rating=payload.rating,
        comment=payload.comment,
        author_user_id=context.user.id,
    )
    return ReviewOut.model_validate(review)


@router.put("/{application_id}/notes", response_model=ApplicantOut)
async def set_notes(
    job_slug: str,
    application_id: uuid.UUID,
    payload: NotesIn,
    context: TenantContext = CanShortlist,
    db: AsyncSession = Depends(get_db_session),
) -> ApplicantOut:
    """Your own private note on an applicant (up to 2,000 characters; blank clears it).

    The candidate never sees it in the product; a person may ask for a copy of what is held about
    them (the data export), so write what you would stand behind.
    """
    row = await employer_service.set_notes_and_reload(
        db, context.tenant.id, job_slug, application_id, payload.notes
    )
    rated = await reviewed_ids(db, [row[0].id], "worker")
    return applicant_out(*row, reviewed=row[0].id in rated)
