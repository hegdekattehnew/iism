from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from api.core.clock import today_ist

BatchPhase = Literal["draft", "open", "full", "running", "finished", "cancelled"]
BatchMode = Literal["in_person", "hybrid", "online"]
CancelReason = Literal[
    "by_organisation", "arrangement_ended", "course_unavailable", "centre_closed"
]

MAX_SEATS = 5000


def _blank_is_none(v: str | None) -> str | None:
    return (v or "").strip() or None


class BatchFields(BaseModel):
    """What an organisation writes about a run. **Input carries the constraints** (the convention):
    the dates are checked against each other here and against today, the seats against the ceiling
    the database also holds."""

    label: Annotated[str | None, Field(max_length=120)] = None
    starts_on: date
    ends_on: date
    seats: Annotated[int, Field(ge=1, le=MAX_SEATS)]
    mode: BatchMode = "in_person"
    schedule: Annotated[str | None, Field(max_length=200)] = None
    # The centre's own statement of the fee for this run; absent means "the course's fee".
    fee_inr: Annotated[int | None, Field(ge=0, le=10_000_000)] = None

    @field_validator("label", "schedule", mode="after")
    @classmethod
    def _blank(cls, v: str | None) -> str | None:
        return _blank_is_none(v)

    @model_validator(mode="after")
    def _ordered(self) -> "BatchFields":
        if self.ends_on < self.starts_on:
            raise ValueError("The last day cannot be before the first day")
        return self

    @model_validator(mode="after")
    def _not_in_the_past(self) -> "BatchFields":
        # A run that has already begun is not planned, it is happening: made after the fact it
        # would show learners a class they cannot join. IST, the learner's own calendar.
        if self.starts_on < today_ist():
            raise ValueError("The first day cannot be in the past")
        return self


class BatchIn(BatchFields):
    course_slug: Annotated[str, Field(min_length=1, max_length=200)]
    # Required inside an organisation (which centre?); a centre's own manager omits it.
    centre_slug: Annotated[str | None, Field(max_length=200)] = None


class BatchUpdateIn(BatchFields):
    """The course and the centre are fixed once a batch exists: a different course or a different
    place is a different batch, and the learners who registered for this one did not choose that."""


class BatchOrgOut(BaseModel):
    slug: str
    name: str
    is_verified: bool = False


class BatchCentreOut(BaseModel):
    slug: str
    name: str
    location_state: str | None = None
    location_district: str | None = None
    # **The centre's own mark**, "address checked": never its organisation's.
    is_verified: bool = False


class BatchCourseOut(BaseModel):
    slug: str
    title: str
    fee_inr: int | None = None
    # Published and not taken down. A batch of a course that is not live cannot be published, and
    # one that was published reads as unavailable to learners (Sprint 100).
    available: bool = True
    provider: BatchOrgOut
    # The course is the delivering organisation's own: no authorisation was needed.
    own: bool = True


class BatchOut(BaseModel):
    id: str
    course: BatchCourseOut
    centre: BatchCentreOut
    # Who runs it: the organisation the centre belongs to ("Delivered by").
    organisation: BatchOrgOut
    label: str | None = None
    starts_on: date
    ends_on: date
    seats: int
    # Derived: seats minus the learners enrolled; never a stored counter.
    enrolled: int = 0
    seats_left: int
    interested: int = 0
    mode: BatchMode
    schedule: str | None = None
    fee_inr: int | None = None
    # The fee a learner would pay: the batch's own statement when there is one, else the course's.
    # `fee_is_override` says which, so the page can label it "set by the centre".
    fee_effective: int | None = None
    fee_is_override: bool = False
    status: Literal["draft", "published", "cancelled"]
    phase: BatchPhase
    cancel_reason: CancelReason | None = None
    published_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime | None = None


class BatchList(BaseModel):
    items: list[BatchOut]
    # The number matching the filter, counted where the rows are; never the page length.
    total: int
    limit: int
    offset: int


class DeliverableCourseOut(BaseModel):
    """A course this organisation may make a batch of: its own, or one it may deliver."""

    slug: str
    title: str
    fee_inr: int | None = None
    provider: BatchOrgOut
    own: bool


class DeliverableCourses(BaseModel):
    items: list[DeliverableCourseOut]
    total: int


class BatchOverview(BaseModel):
    """What a delivering organisation (or a centre) has to look at today: counts first, then the
    next few that start. Every figure is counted where the rows are, never read off a page."""

    drafts: int
    starting_soon: int
    running: int
    # Seats not yet taken in published batches that start within a fortnight, and how many batches
    # they are in: the work of filling a class is the work of the weeks before it starts.
    unfilled_seats: int
    unfilled_batches: int
    # Batches not yet over whose course is not published (the page warns; learners cannot see them).
    unavailable: int
    upcoming: list[BatchOut]


class OrgCourseRef(BaseModel):
    slug: str
    title: str


class CourseBatchesRowOut(BaseModel):
    """One course of the seller's, as one delivering organisation runs it: counts, no learner."""

    course: OrgCourseRef
    organisation: BatchOrgOut
    batches: int
    open: int
    full: int
    running: int
    finished: int
    seats: int
    enrolled: int


class CourseBatchesOut(BaseModel):
    items: list[CourseBatchesRowOut]
    total: int


class BatchBulkRowOut(BaseModel):
    row: int
    status: Literal["ok", "warning", "error", "skip"]
    course: str | None = None
    centre: str | None = None
    messages: list[str] = Field(default_factory=list)
    # The batch a skipped row matched, or the one an applied row made.
    id: str | None = None
    created: bool = False


class BatchBulkReportOut(BaseModel):
    applied: bool
    rows: list[BatchBulkRowOut]
    notes: list[str]
    ok: int
    warnings: int
    errors: int
    skipped: int
    created: int
    errors_csv: str | None = None


class BatchBulkPublishIn(BaseModel):
    ids: Annotated[list[str], Field(min_length=1, max_length=200)]


class BatchBulkPublishRowOut(BaseModel):
    id: str
    published: bool
    message: str | None = None


class BatchBulkPublishOut(BaseModel):
    results: list[BatchBulkPublishRowOut]
    published: int
    refused: int
