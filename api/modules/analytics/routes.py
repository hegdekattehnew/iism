"""Events the client has to report, because the server cannot see them.

ADR-025 names candidate-to-course click-through as one of three metrics that
substitute for a revenue signal while v1 is free. `course_opened` has been in
`EVENT_NAMES` since Sprint 10 and **nothing had ever emitted it** until this
route, so that metric was unmeasurable the whole time — which is worse than
not claiming it, because the name in the enum reads like the thing exists.

`course_dismissed` (Sprint 33, BL-2.2) is its negative half: `scope-
reconciliation.md` #3 found precision@5 had a positive signal only, "shown and
opened" and "shown, opened and four explicitly rejected" being the same rows.

Every other event is recorded server-side from a request that already happened.
These cannot be: following a link out of a recommendation, or dismissing one,
is a client-side act, and inferring either from a later request would
attribute organic behaviour to a recommendation that had nothing to do with it.

Each gets its own handler, because `record()` commits and must not run
alongside other uncommitted work.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.analytics.schemas import CourseDismissedIn, CourseOpenedIn
from api.modules.analytics.service import record_course_dismissed, record_course_opened
from api.modules.identity.models import User

router = APIRouter(prefix="/me/events", tags=["analytics"])


@router.post("/course-opened", status_code=status.HTTP_204_NO_CONTENT)
async def course_opened(
    payload: CourseOpenedIn,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    await record_course_opened(
        db,
        user_id=user.id,
        course_slug=payload.course_slug,
        from_job_slug=payload.from_job_slug,
    )


@router.post("/course-dismissed", status_code=status.HTTP_204_NO_CONTENT)
async def course_dismissed(
    payload: CourseDismissedIn,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    """The "not interested" signal (Sprint 33, BL-2.2) -- a client-side act
    the server cannot infer any other way, the same reason `course-opened`
    has its own endpoint rather than being derived from a later request."""
    await record_course_dismissed(
        db,
        user_id=user.id,
        course_slug=payload.course_slug,
        from_job_slug=payload.from_job_slug,
    )
