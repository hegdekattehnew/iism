import uuid
from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from api.modules.applications.models import APPLICATION_STATUSES, EMPLOYER_STATUSES
from api.modules.identity import TenantOut

# Closed on the way out so the generated TypeScript client types a status as a
# union rather than `string`; `tests/test_enumerations.py` holds it to the CHECK.
ApplicationStatus = Literal["applied", "withdrawn", "shortlisted", "rejected", "hired"]
EmployerStatus = Literal["shortlisted", "rejected", "hired"]

# The unions above and the tuples the CHECK is generated from must agree. A
# closed union on an output model is a latent 500 the moment the database holds
# a value it does not list -- twice already in this project.
assert set(get_args(ApplicationStatus)) == set(APPLICATION_STATUSES)  # noqa: S101
assert set(get_args(EmployerStatus)) == set(EMPLOYER_STATUSES)  # noqa: S101


class JobRef(BaseModel):
    """Enough of a vacancy to recognise it in a list of your own applications."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title_en: str
    title_hi: str | None = None
    location_state: str | None = None
    location_district: str | None = None
    employment_type: str
    # The public view of the organisation: `TenantOut` deliberately carries no
    # contact email, and this payload is no place to start.
    tenant: TenantOut


class ApplicationIn(BaseModel):
    job_slug: str = Field(max_length=200)
    # A covering note, not a CV. Bounded here rather than at the column, the
    # same way every other free-prose input in this project is.
    message: str | None = Field(None, max_length=1_000)


class ApplicationOut(BaseModel):
    """The candidate's own view of an application."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job: JobRef
    status: ApplicationStatus
    message: str | None = None
    applied_at: datetime
    updated_at: datetime


class SavedJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job: JobRef
    saved_at: datetime
