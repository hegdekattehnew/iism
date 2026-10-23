import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AuthorisationState = Literal["requested", "approved", "declined", "revoked"]
Side = Literal["provider", "partner"]


class OrgRefOut(BaseModel):
    """An organisation as a counterparty sees it: its public face and nothing else."""

    slug: str
    name: str
    city: str | None = None
    is_verified: bool = False


class CourseRefOut(BaseModel):
    slug: str
    title: str


class AuthorisationOut(BaseModel):
    """One arrangement, **as the organisation asking sees it**.

    `side` is what the asking organisation is in it (the course's seller, or the one delivering),
    `other` is the organisation on the other side, and `course` is `None` for "every course the
    seller has". What the viewer may do about it is the client's to read off `state`, `side` and
    `initiated_by` (the server refuses anything else), never a flag the server could get wrong.
    """

    id: uuid.UUID
    state: AuthorisationState
    side: Side
    initiated_by: Side
    other: OrgRefOut
    course: CourseRefOut | None = None
    requested_at: datetime
    approved_at: datetime | None = None
    ended_at: datetime | None = None
    ended_by_side: Side | None = None


class DeliveryOut(BaseModel):
    """Every arrangement an organisation is in, on both sides (an organisation may be both)."""

    as_partner: list[AuthorisationOut] = Field(default_factory=list)
    as_provider: list[AuthorisationOut] = Field(default_factory=list)


class DeliveryAskIn(BaseModel):
    """Ask to deliver, or invite to deliver: the other organisation's slug, and the scope.

    `course_slug` absent or null means every course the seller has.
    """

    organisation_slug: str = Field(min_length=1, max_length=160)
    course_slug: str | None = Field(default=None, max_length=200)


class TrainingOrganisationList(BaseModel):
    items: list[OrgRefOut]
    total: int


class DeliveredCourseOut(BaseModel):
    """A course an organisation is **authorised** to deliver, and whose it is."""

    provider: OrgRefOut
    course: CourseRefOut | None = None


class DeliveredOut(BaseModel):
    items: list[DeliveredCourseOut] = Field(default_factory=list)
