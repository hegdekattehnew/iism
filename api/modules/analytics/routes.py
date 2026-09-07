"""The one event the client has to report, because the server cannot see it.

ADR-025 names candidate-to-course click-through as one of three metrics that
substitute for a revenue signal while v1 is free. `course_opened` has been in
`EVENT_NAMES` since Sprint 10 and **nothing has ever emitted it**, so that
metric has been unmeasurable the whole time — which is worse than not claiming
it, because the name in the enum reads like the thing exists.

Every other event is recorded server-side from a request that already happened.
This one cannot be: following a link out of a recommendation is a client-side
act, and inferring it from a later `GET /courses/{slug}` would attribute organic
browsing to a recommendation that had nothing to do with it.

Its own handler, because `record()` commits and must not run alongside other
uncommitted work.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.analytics.schemas import CourseOpenedIn
from api.modules.analytics.service import record
from api.modules.identity.models import User
from api.modules.marketplace.models import Course

router = APIRouter(prefix="/me/events", tags=["analytics"])


@router.post("/course-opened", status_code=status.HTTP_204_NO_CONTENT)
async def course_opened(
    payload: CourseOpenedIn,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    course_id = await db.scalar(select(Course.id).where(Course.slug == payload.course_slug))
    if course_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")

    await record(
        db,
        "course_opened",
        user_id=user.id,
        subject_type="course",
        subject_id=course_id,
        # Which gap it was opened from, so click-through can be attributed to a
        # recommendation rather than counted in aggregate. A slug, not free text.
        payload={"from_job": payload.from_job_slug} if payload.from_job_slug else None,
    )
