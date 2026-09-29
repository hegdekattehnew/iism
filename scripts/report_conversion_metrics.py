"""Report the two ADR-025 metrics that `make evaluate` does not cover.

ADR-025 names three metrics that must be citable before any billing code is
written: recommendation precision@5, candidate-to-course click-through, and
provider-reported enrolment conversion. `make evaluate` already answers the
first from the hand-labelled golden set and touches no `analytics_events` row.
This answers the other two, and only those two -- it is a sibling command, not
a replacement, for the same reason `evaluate_matching.py` reads only the
golden set: each metric already has the tool built for it.

**This prints the real number, however small.** ADR-043 recorded that
click-through was "joinable, not populated" because the platform has no real
user volume -- that is still true, and will read as near-zero until real
traffic exists. Nothing here manufactures a better-looking number; the
question this script exists to answer honestly is only whether the query is
correct, not whether the answer is impressive yet.
"""

import asyncio

from sqlalchemy import func, select

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.analytics.models import AnalyticsEvent
from api.modules.interests.models import CourseInterest


async def _course_pairs(db, event_name: str) -> set[tuple]:  # type: ignore[no-untyped-def]
    """Distinct `(user_id, course_id)` pairs behind one event name.

    Filtered to `subject_type="course"` explicitly: `course_recommended` and
    `course_opened` rows written before migration 0025 share the event name
    with a `subject_type="job"` cohort that is not backfilled (`matching/
    service.py`'s own docstring on the point), so an unfiltered count would
    silently include pairs that were never about a course at all.
    """
    rows = await db.execute(
        select(AnalyticsEvent.user_id, AnalyticsEvent.subject_id)
        .where(
            AnalyticsEvent.name == event_name,
            AnalyticsEvent.subject_type == "course",
            AnalyticsEvent.user_id.is_not(None),
        )
        .distinct()
    )
    return set(rows.all())


async def click_through(db) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """`(recommended, opened)` distinct `(user_id, course_id)` pairs."""
    recommended_pairs = await _course_pairs(db, "course_recommended")
    opened_pairs = await _course_pairs(db, "course_opened")
    return len(recommended_pairs), len(recommended_pairs & opened_pairs)


async def enrolment_conversion(db) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """`(total, enrolled)` `CourseInterest` rows, platform-wide.

    `enrolled` is provider-reported and unverified -- the same trust level
    `contacted` already carries (`interests/models.py`) -- so this counts
    what providers claimed, not a fact the platform independently confirmed.
    """
    total = await db.scalar(select(func.count()).select_from(CourseInterest))
    enrolled = await db.scalar(
        select(func.count()).select_from(CourseInterest).where(CourseInterest.status == "enrolled")
    )
    return total or 0, enrolled or 0


async def main() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        recommended, opened = await click_through(db)
        total_interests, enrolled = await enrolment_conversion(db)

    print("ADR-025 conversion metrics (see ADR-047 for what this does and does not close)")
    print()
    if recommended:
        print(
            f"click-through:          {opened}/{recommended} distinct (user, course) pairs "
            f"opened after being recommended ({opened / recommended:.1%})"
        )
    else:
        print(
            "click-through:          0 recommended, 0 opened -- "
            "no candidate has been shown a course yet"
        )

    if total_interests:
        print(
            f"enrolment conversion:   {enrolled}/{total_interests} course interests reported "
            f"enrolled ({enrolled / total_interests:.1%})"
        )
    else:
        print("enrolment conversion:   0 interests recorded -- nothing to convert yet")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
