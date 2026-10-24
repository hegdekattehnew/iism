"""What a batch is today, from what was decided and what is true (Sprint 98, ADR-103).

Pure: no I/O, no clock (the date is a parameter), no model. The stored status is only what a person
decided (`draft`, `published`, `cancelled`); this is the rest, and it is derived so it can never
disagree with the calendar or the seats.

    draft       not live; nobody can see it but the organisation
    open        published, has not started, has a seat free
    full        published, has not started, no seat free
    running     published and started, not yet over -- **never** stopped from under its learners
    finished    published and its last day has passed
    cancelled   decided against, with a reason

A batch is **joinable** only while `open`. A full batch stays visible (a learner should know there
was one) and a running one is history in the making, not a place to join.
"""

from datetime import date
from typing import Literal

Phase = Literal["draft", "open", "full", "running", "finished", "cancelled"]
PHASES: tuple[Phase, ...] = ("draft", "open", "full", "running", "finished", "cancelled")

# Phases in which a batch can still be changed or cancelled **without** reaching into a class
# already in progress. A running batch finishes (ADR-103).
CANCELLABLE: frozenset[Phase] = frozenset({"draft", "open", "full"})


def phase(
    *, status: str, starts_on: date, ends_on: date, seats: int, enrolled: int, today: date
) -> Phase:
    if status == "cancelled":
        return "cancelled"
    if status != "published":
        return "draft"
    if ends_on < today:
        return "finished"
    if starts_on <= today:
        return "running"
    return "full" if enrolled >= seats else "open"


def seats_left(*, seats: int, enrolled: int) -> int:
    """Never negative: an organisation that lowered the seats under the enrolled is refused, but a
    row written by hand or an import still reads as zero, not as a debt."""
    return max(0, seats - enrolled)
