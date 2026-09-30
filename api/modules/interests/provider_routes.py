import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.modules.interests import provider_service
from api.modules.interests.schemas import (
    CourseInterestCount,
    CourseRef,
    InterestedLearnerOut,
    InterestedLearnerPage,
    ProviderDashboardOut,
    ProviderStatusIn,
)

# Course providers only, and only their own courses. `require` asks both
# questions in one declaration -- a guard a handler must remember to call is
# one that eventually is not called (Sprint 15). `publishes="course"` resolves
# to `course_provider`, so an employer is refused here exactly as a provider is
# refused the candidate pool.
router = APIRouter(prefix="/org/{org_slug}", tags=["interests"])
CanContactLearners = Depends(require(Permission.LEARNER_CONTACT, "course"))


def _learner(interest, profile, user) -> InterestedLearnerOut:  # type: ignore[no-untyped-def]
    """One interested learner, with the disclosure attached.

    One construction site, because the rule that contact disappears on
    withdrawal is a property of this function and nothing else. A withdrawn row
    keeps its date and its status and loses the person entirely -- not even a
    reference, which `candidate_card()` alone is allowed to mint.
    """
    live = interest.contact_is_visible
    return InterestedLearnerOut(
        interest_id=interest.id,
        status=interest.status,
        registered_at=interest.created_at,
        message=interest.message if live else None,
        location_state=profile.location_state if live else None,
        location_district=profile.location_district if live else None,
        contact=(
            {"full_name": user.full_name, "phone": user.phone, "email": user.email}
            if live
            else None
        ),
    )


@router.get("/interests/dashboard", response_model=ProviderDashboardOut)
async def provider_dashboard(
    context: TenantContext = CanContactLearners,
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> ProviderDashboardOut:
    """A course provider's landing numbers (Sprint 39, BL-10.3), and the
    per-course breakdown behind them (Sprint 40).

    **Not** `/org/{org_slug}/courses/dashboard`: `course_publishing_routes.py`
    (registered earlier in `main.py`) already owns `/org/{org_slug}/courses/
    {slug}` as a catch-all single-course lookup, and a literal segment
    declared first *within this router* cannot rescue a path a different
    router's dynamic route already intercepts app-wide -- route matching is
    ordered across every included router, not per module. `/interests/...`
    is this module's own path segment, with no such collision.

    A distinct path from the employer's own `/org/{org_slug}/dashboard`
    either way, since one route cannot serve both without branching on
    tenant type mid-handler, which `require(..., "course")` already exists
    to avoid.

    `courses` is built the same way `interest_by_course` builds its own list
    -- localised titles via `overrides_for`, never the raw `Course.title` on
    a Hindi page."""
    data = await provider_service.provider_dashboard(db, context.tenant.id)
    overrides = await overrides_for(
        db, "course", [c for c, _, _ in data.courses], ("title",), locale
    )
    return ProviderDashboardOut(
        published_courses=data.published_courses,
        interested_live=data.interested_live,
        interested_total=data.interested_total,
        enrolled=data.enrolled,
        conversion_rate=data.conversion_rate,
        courses=[
            CourseInterestCount(
                course_slug=course.slug,
                course_title=overrides.get(course.id, {}).get("title", course.title),
                live=live,
                total=total,
            )
            for course, live, total in data.courses
        ],
    )


@router.get("/courses/{course_slug}/interests", response_model=InterestedLearnerPage)
async def list_interested_learners(
    course_slug: str,
    context: TenantContext = CanContactLearners,
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> InterestedLearnerPage:
    """Who wants this course, with how to reach them while each interest is live."""
    course, rows = await provider_service.interested_learners(db, context.tenant.id, course_slug)
    overrides = await overrides_for(db, "course", [course], ("title",), locale)
    items = [_learner(*row) for row in rows]
    return InterestedLearnerPage(
        course=CourseRef.model_validate(course).model_copy(update=overrides.get(course.id, {})),
        items=items,
        total=len(items),
    )


@router.patch("/courses/{course_slug}/interests/{interest_id}", response_model=InterestedLearnerOut)
async def set_interest_status(
    course_slug: str,
    interest_id: uuid.UUID,
    payload: ProviderStatusIn,
    context: TenantContext = CanContactLearners,
    db: AsyncSession = Depends(get_db_session),
) -> InterestedLearnerOut:
    """Mark that you have been in touch. A withdrawn interest cannot be moved."""
    return _learner(
        *await provider_service.set_status_and_reload(
            db, context.tenant.id, course_slug, interest_id, payload.status
        )
    )


@router.get("/interests", response_model=list[CourseInterestCount])
async def interest_by_course(
    context: TenantContext = CanContactLearners,
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> list[CourseInterestCount]:
    """How much interest each of this provider's courses has attracted."""
    rows = await provider_service.counts_by_course(db, context.tenant.id)
    overrides = await overrides_for(db, "course", [c for c, _, _ in rows], ("title",), locale)
    return [
        CourseInterestCount(
            course_slug=course.slug,
            course_title=overrides.get(course.id, {}).get("title", course.title),
            live=live,
            total=total,
        )
        for course, live, total in rows
    ]
