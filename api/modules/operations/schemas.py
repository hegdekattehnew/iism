import uuid
from datetime import datetime
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from api.modules.operations.models import VERIFICATION_DECISIONS

VerificationDecision = Literal["granted", "revoked"]

# The union and the tuple the CHECK is generated from must agree, for the
# reason `tests/test_enumerations.py` exists: a widened constraint is invisible
# both to autogenerate and to the schema beside it.
assert set(get_args(VerificationDecision)) == set(VERIFICATION_DECISIONS)  # noqa: S101


class UnverifiedOrganisation(BaseModel):
    """One row of the queue: enough to decide without opening anything else."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    tenant_type: str
    city: str | None = None
    website: str | None = None
    created_at: datetime
    # What the organisation has actually done here. An operator verifying an
    # employer with no vacancies and no members is verifying an intention.
    jobs: int
    courses: int
    members: int


class VerificationIn(BaseModel):
    """Grant or revoke, with the evidence. One route, because they are one
    decision with two values and a second endpoint would duplicate the note."""

    decision: VerificationDecision
    # Ten characters is not a formality: this is the only record of why a
    # candidate should believe the badge, and "ok" is not a reason. Mirrored on
    # the form and asserted by `web/src/lib/constraints.test.ts`.
    note: Annotated[str, Field(min_length=10, max_length=500)]


class VerificationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    decision: VerificationDecision
    note: str
    created_at: datetime
    # Null once that operator has exercised their own erasure. The client
    # renders "a former operator" rather than inventing a name.
    actor_name: str | None = None


class OrganisationVerificationOut(BaseModel):
    """The organisation's current badge, and every decision behind it."""

    slug: str
    name: str
    is_verified: bool
    verified_at: datetime | None = None
    verification_note: str | None = None
    history: list[VerificationEventOut]
