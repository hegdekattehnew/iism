import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CentreStatus = Literal["active", "closed"]


class CentreIn(BaseModel):
    """A centre as an organisation writes it.

    The place is **required and written as text** (`state`, `district`): where a centre is decides
    which learners it can reach, so it is asked for; and it is resolved against the geography master
    by the service, where an unresolvable name is kept as written and flagged rather than guessed
    (no id is better than a wrong one). The address is the street address a learner would walk to.
    """

    name: Annotated[str, Field(min_length=2, max_length=120)]
    address: Annotated[str | None, Field(max_length=500)] = None
    state: Annotated[str, Field(min_length=2, max_length=120)]
    district: Annotated[str, Field(min_length=2, max_length=120)]

    @field_validator("name", "state", "district", mode="after")
    @classmethod
    def _stripped(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("must have at least 2 characters")
        return v

    @field_validator("address", mode="after")
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        return (v or "").strip() or None


class CentreOut(BaseModel):
    """One centre, as its organisation sees it.

    `status` is **derived** from `closed_at`, never stored beside it. `is_verified` is **the
    centre's own mark** ("address checked"), not its organisation's: they are different claims
    (ADR-102), and a verified organisation never makes a centre verified.
    """

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    address: str | None = None
    location_state: str | None = None
    location_district: str | None = None
    place_resolved: bool = False
    status: CentreStatus = "active"
    closed_at: datetime | None = None
    is_verified: bool = False
    created_at: datetime | None = None


class CentreList(BaseModel):
    items: list[CentreOut]
    total: int
    active: int
    limit: int


class CentreBulkRowOut(BaseModel):
    row: int
    status: Literal["ok", "warning", "error", "skip"]
    name: str | None = None
    messages: list[str] = Field(default_factory=list)
    slug: str | None = None
    created: bool = False


class CentreBulkReportOut(BaseModel):
    applied: bool
    rows: list[CentreBulkRowOut]
    notes: list[str] = Field(default_factory=list)
    ok: int
    warnings: int
    errors: int
    skipped: int
    created: int
    remaining: int
    errors_csv: str | None = None


# Re-exported so a route and a test name one type.
CentreId = uuid.UUID
