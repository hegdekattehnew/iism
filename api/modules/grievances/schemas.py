import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, TypeAdapter, field_validator

from api.modules.grievances.models import BODY_MAX, BODY_MIN
from api.modules.identity.schemas import normalise_email, normalise_phone

Kind = Literal["contact", "grievance", "data_request"]
Status = Literal["open", "acknowledged", "resolved", "dismissed"]

_EMAIL = TypeAdapter(EmailStr)


def _reply_to(value: str) -> str:
    """An email address or an Indian mobile number, in the one form the rest of the product uses."""
    value = value.strip()
    if "@" in value:
        return normalise_email(str(_EMAIL.validate_python(value)))
    phone = normalise_phone(value)
    if not re.fullmatch(r"\+91[6-9]\d{9}", phone):
        raise ValueError("Give an email address or a ten-digit mobile number to write back to.")
    return phone


class GrievanceIn(BaseModel):
    kind: Kind
    body: Annotated[str, Field(min_length=BODY_MIN, max_length=BODY_MAX)]
    # Required when signed out (the service says so); ignored for somebody signed in, who is
    # answered through their account.
    reply_to: Annotated[str, Field(max_length=254)] | None = None
    # A honeypot: a field no person sees or fills. A bot that fills every field announces itself.
    website: Annotated[str, Field(max_length=200)] | None = None

    @field_validator("body", mode="after")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if len(v.strip()) < BODY_MIN:
            raise ValueError(f"Write at least {BODY_MIN} characters.")
        return v.strip()

    @field_validator("reply_to", mode="after")
    @classmethod
    def _address(cls, v: str | None) -> str | None:
        return _reply_to(v) if v and v.strip() else None


class GrievanceSubmittedOut(BaseModel):
    reference: str
    kind: Kind
    acknowledge_within_hours: int
    resolve_within_days: int


class GrievanceOut(BaseModel):
    """A person's own message, and where it stands."""

    reference: str
    kind: Kind
    status: Status
    created_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class GrievanceAccountOut(BaseModel):
    """Who the signed-in sender is, masked: enough to find the account, not to dial or write."""

    phone: str | None = None
    email: str | None = None


class GrievanceQueueItem(BaseModel):
    id: uuid.UUID
    reference: str
    kind: Kind
    status: Status
    body: str
    reply_to: str | None = None
    account: GrievanceAccountOut | None = None
    created_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    # Against what the grievance page promises (one setting each), so the badge and the page
    # cannot disagree.
    overdue_acknowledge: bool
    overdue_resolve: bool


class GrievanceQueueOut(BaseModel):
    items: list[GrievanceQueueItem]
    open: int
    overdue: int


class GrievanceDecisionIn(BaseModel):
    note: Annotated[str, Field(min_length=10, max_length=1000)]
