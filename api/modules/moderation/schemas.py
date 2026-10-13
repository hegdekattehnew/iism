import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from api.modules.moderation.models import DETAIL_MAX

TargetType = Literal["job", "course"]
ReportReason = Literal[
    "asks_for_money",
    "fake_or_misleading",
    "discriminatory",
    "unsafe_or_illegal",
    "spam_or_duplicate",
    "other",
]
ReportStatus = Literal["open", "dismissed", "actioned"]

NOTE_MIN, NOTE_MAX = 10, 1000


class ReportIn(BaseModel):
    reason: ReportReason
    detail: Annotated[str, Field(max_length=DETAIL_MAX)] | None = None

    @field_validator("detail")
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None


class ReportReceivedOut(BaseModel):
    """All the reporter is told: that it arrived. Not what became of it (ADR-069)."""

    received: bool = True


class ReporterOut(BaseModel):
    """Masked, as in the grievance queue: enough to correlate, not enough to identify or dial."""

    phone: str | None = None
    email: str | None = None


class ReportOut(BaseModel):
    reason: ReportReason
    detail: str | None = None
    reporter: ReporterOut | None = None
    created_at: datetime


class OrganisationRefOut(BaseModel):
    slug: str
    name: str


class ListingReportsOut(BaseModel):
    """One listing and everything said about it.

    An operator decides about a listing, not a report."""

    target_type: TargetType
    target_id: uuid.UUID
    slug: str
    title: str
    organisation: OrganisationRefOut | None = None
    status: Literal["draft", "published"]
    open_reports: int
    reasons: dict[str, int] = Field(default_factory=dict)
    oldest: datetime | None = None
    reports: list[ReportOut] = Field(default_factory=list)
    taken_down_at: datetime | None = None
    takedown_reason: str | None = None


class ReportQueueOut(BaseModel):
    items: list[ListingReportsOut]
    # How many listings have an open report, however many are shown.
    open_listings: int
    taken_down: int


class DismissIn(BaseModel):
    note: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=NOTE_MIN, max_length=NOTE_MAX)
    ]


class TakedownIn(BaseModel):
    # Shown to the organisation, which is emailed it. The form says so.
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=NOTE_MIN, max_length=NOTE_MAX)
    ]


class DecisionOut(BaseModel):
    target_type: TargetType
    target_id: uuid.UUID
    reports_closed: int = 0
    taken_down: bool
