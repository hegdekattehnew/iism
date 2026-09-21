import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.localisation import overrides_for, request_locale
from api.modules.identity import User, get_current_candidate
from api.modules.interests import service
from api.modules.interests.schemas import CourseRef, InterestIn, InterestOut

# `get_current_candidate`, not `get_current_user`: wanting to train is the
# learner's side of the marketplace, and an organisation-only account that
# never asked for a candidate profile should not have one created by pressing
# a button on a course page.
router = APIRouter(prefix="/me", tags=["interests"])


def _out(interest, titles: dict | None = None) -> InterestOut:  # type: ignore[no-untyped-def]
    """`titles` carries the course's translated title, when there is one.

    Resolved by the caller rather than here: one query for a whole list, not
    one per row (ADR-041). The jobs equivalent was missed on the first pass and
    /hi/applications quietly showed English titles until the browser said so.
    """
    course = CourseRef.model_validate(interest.course)
    if titles:
        course = course.model_copy(update=titles)
    return InterestOut(
        id=interest.id,
        course=course,
        status=interest.status,
        message=interest.message,
        registered_at=interest.created_at,
        updated_at=interest.updated_at,
    )


@router.post("/course-interests", response_model=InterestOut, status_code=status.HTTP_201_CREATED)
async def register_interest(
    payload: InterestIn,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> InterestOut:
    """Tell a provider you want this course, sharing your name and contact."""
    interest = await service.register(
        db, user, course_slug=payload.course_slug, message=payload.message
    )
    overrides = await overrides_for(db, "course", [interest.course], ("title",), locale)
    return _out(interest, overrides.get(interest.course_id))


@router.get("/course-interests", response_model=list[InterestOut])
async def my_interests(
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> list[InterestOut]:
    interests = await service.list_interests(db, user)
    overrides = await overrides_for(db, "course", [i.course for i in interests], ("title",), locale)
    return [_out(i, overrides.get(i.course_id)) for i in interests]


@router.post("/course-interests/{interest_id}/withdraw", response_model=InterestOut)
async def withdraw_interest(
    interest_id: uuid.UUID,
    user: User = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db_session),
    locale: str = Depends(request_locale),
) -> InterestOut:
    """Take it back. The provider keeps the fact and loses the contact details."""
    interest = await service.withdraw(db, user, interest_id)
    overrides = await overrides_for(db, "course", [interest.course], ("title",), locale)
    return _out(interest, overrides.get(interest.course_id))
