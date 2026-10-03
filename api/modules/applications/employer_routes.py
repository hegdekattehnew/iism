import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.modules.applications import employer_service, review_service
from api.modules.applications.schemas import (
    ApplicantOut,
    ApplicantPage,
    ContactOut,
    EmployerDashboardOut,
    JobRef,
    ReviewIn,
    ReviewOut,
    StatusIn,
)
from api.modules.matching import candidate_card
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


def _applicant(application, profile, user, result) -> ApplicantOut:  # type: ignore[no-untyped-def]
    """One applicant, de-identified card plus the disclosure beside it.

    One construction site, because the rule that contact disappears on
    withdrawal is a property of this function and nothing else.
    """
    live = application.contact_is_visible
    return ApplicantOut(
        application_id=application.id,
        status=application.status,
        applied_at=application.created_at,
        # The candidate's own words are part of what withdrawing takes back,
        # exactly as `interests.provider_routes._learner` already does.
        message=application.message if live else None,
        candidate=candidate_card(profile, result),
        contact=(
            ContactOut(full_name=user.full_name, phone=user.phone, email=user.email)
            if live
            else None
        ),
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
    items = [_applicant(*row) for row in rows]
    return ApplicantPage(
        job=JobRef.model_validate(job).model_copy(update=overrides.get(job.id, {})),
        items=items,
        total=len(items),
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
    return _applicant(
        *await employer_service.set_status_and_reload(
            db, context.tenant.id, job_slug, application_id, payload.status
        )
    )


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
