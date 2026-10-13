"""Can this person actually take this course? (Sprint 58, BL-14.6, ADR-068)

`courses_closing_gap` used to rank by how much of a gap a course closes and stop there, so an
offline course in another state, one that started last month and one with no seat left were all
recommended exactly like the course next door. This is the other half of "recommend a course":
whether the person can act on it.

**Pure, like `scoring.py`**: no I/O, no clock and no settings. The date is a parameter and the
context is a value built at the service boundary. And it is **not part of the score** (ADR-037):
nothing here changes a match percentage. It orders and labels suggestions that were already chosen
by what they teach.

Nothing is hidden. A course that is far away, started, full or over budget stays in the list and is
labelled, because it may be the only one that teaches the missing standard and intakes are often
rolling. And **an unknown place is neutral**: a provider who gave none (every course published
before Sprint 58) is neither promoted nor buried, and a candidate with no location on file gets no
reordering from place at all -- "no evidence" must not read as "far away".
"""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Literal

Reach = Literal["online", "district", "state", "unknown", "elsewhere"]

# Lower sorts first. Online and in-district are equally easy to attend; "unknown" sits between "in
# your state" and "elsewhere" because it is neither evidence for nor against.
REACH_RANK: dict[Reach, int] = {
    "online": 0,
    "district": 0,
    "state": 1,
    "unknown": 2,
    "elsewhere": 3,
}


@dataclass(frozen=True)
class CourseFacts:
    """What attendability reads off a course, and nothing else."""

    mode: str
    state_id: uuid.UUID | None
    district_id: uuid.UUID | None
    starts_on: date | None
    seats_left: int | None
    fee_inr: int | None


@dataclass(frozen=True)
class AttendContext:
    """Who is asking, where they would go and what they would pay.

    `states` and `districts` are the candidate's own and their preferred ones (the same facts
    `candidate_facts` gives the job-side locality tie-break). `budget_inr` is per request and never
    stored: a profile column would need export and erasure treatment.
    """

    states: frozenset[uuid.UUID]
    districts: frozenset[uuid.UUID]
    budget_inr: int | None
    today: date


@dataclass(frozen=True)
class Attendance:
    reach: Reach
    started: bool
    full: bool
    # `None` when no budget was given, so "unknown" is never confused with "over".
    within_budget: bool | None
    attendable: bool


def assess(course: CourseFacts, context: AttendContext) -> Attendance:
    reach = _reach(course, context)
    started = course.starts_on is not None and course.starts_on < context.today
    full = course.seats_left == 0
    # A course with no stated fee is treated as free, as the course page shows it.
    within_budget = (
        None if context.budget_inr is None else (course.fee_inr or 0) <= context.budget_inr
    )
    return Attendance(
        reach=reach,
        started=started,
        full=full,
        within_budget=within_budget,
        attendable=reach != "elsewhere" and not started and not full and within_budget is not False,
    )


def _reach(course: CourseFacts, context: AttendContext) -> Reach:
    if course.mode == "online":
        return "online"
    if course.state_id is None and course.district_id is None:
        return "unknown"
    if not context.states and not context.districts:
        # Nothing known about the person: no evidence either way.
        return "unknown"
    if course.district_id is not None and course.district_id in context.districts:
        return "district"
    if course.state_id is not None and course.state_id in context.states:
        return "state"
    return "elsewhere"


def rank_key(
    attendance: Attendance, *, covers_mandatory: int, closes_count: int, title: str
) -> tuple[int, int, int, int, int, str]:
    """The order of suggestions, best first.

    1. **A course that closes a mandatory standard is never outranked by one that does not**,
       however near the other is: a mandatory gap blocks an application, while a nearby course
       that does not unblock one merely improves a score.
    2. Among those, a course the person can attend.
    3. Then the nearer one.
    4. Then by how much of the gap it closes, most mandatory first.
    """
    return (
        0 if covers_mandatory > 0 else 1,
        0 if attendance.attendable else 1,
        REACH_RANK[attendance.reach],
        -covers_mandatory,
        -closes_count,
        title,
    )
