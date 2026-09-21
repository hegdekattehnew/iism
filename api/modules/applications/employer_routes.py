import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.modules.applications import employer_service
from api.modules.applications.schemas import (
    ApplicantOut,
    ApplicantPage,
    ContactOut,
    JobRef,
    StatusIn,
)
from api.modules.matching import candidate_card

# Employers only, and only their own vacancies. `require` asks both questions
# in one declaration -- a guard a handler must remember to call is one that
# eventually is not called (Sprint 15).
router = APIRouter(prefix="/org/{org_slug}/jobs/{job_slug}/applications", tags=["applications"])
CanShortlist = Depends(require(Permission.CANDIDATE_SHORTLIST, "job"))


def _applicant(application, profile, user, result) -> ApplicantOut:  # type: ignore[no-untyped-def]
    """One applicant, de-identified card plus the disclosure beside it.

    One construction site, because the rule that contact disappears on
    withdrawal is a property of this function and nothing else.
    """
    return ApplicantOut(
        application_id=application.id,
        status=application.status,
        applied_at=application.created_at,
        message=application.message,
        candidate=candidate_card(profile, result),
        contact=(
            ContactOut(full_name=user.full_name, phone=user.phone, email=user.email)
            if application.contact_is_visible
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
    """Shortlist, reject or hire. A withdrawn application cannot be moved."""
    await employer_service.set_status(
        db, context.tenant.id, job_slug, application_id, payload.status
    )
    _, rows = await employer_service.inbox(db, context.tenant.id, job_slug)
    return _applicant(*next(r for r in rows if r[0].id == application_id))
