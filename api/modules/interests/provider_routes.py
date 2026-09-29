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
