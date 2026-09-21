import uuid
from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from api.modules.identity import TenantOut
from api.modules.interests.models import INTEREST_STATUSES, PROVIDER_STATUSES

# Closed on the way out so the generated TypeScript client types a status as a
# union rather than `string`; `tests/test_enumerations.py` holds it to the CHECK.
InterestStatus = Literal["registered", "withdrawn", "contacted"]
ProviderStatus = Literal["contacted"]

# The unions above and the tuples the CHECK is generated from must agree. A
# closed union on an output model is a latent 500 the moment the database holds
# a value it does not list -- twice already in this project.
assert set(get_args(InterestStatus)) == set(INTEREST_STATUSES)  # noqa: S101
assert set(get_args(ProviderStatus)) == set(PROVIDER_STATUSES)  # noqa: S101


class CourseRef(BaseModel):
    """Enough of a course to recognise it in a list of your own interests."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    mode: str
    duration_hours: int | None = None
    fee_inr: int | None = None
    # The public view of the organisation: `TenantOut` deliberately carries no
    # contact email, and this payload is no place to start.
    tenant: TenantOut


class InterestIn(BaseModel):
    course_slug: str = Field(max_length=200)
    # What the learner wants the provider to know, not a CV. Bounded here
    # rather than at the column, as every other free-prose input here is.
    message: str | None = Field(None, max_length=1_000)


class InterestOut(BaseModel):
    """The learner's own view of an interest."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course: CourseRef
    status: InterestStatus
    message: str | None = None
    registered_at: datetime
    updated_at: datetime


class LearnerContactOut(BaseModel):
    """The disclosure itself.

    Present only while an interest is live. Defined here rather than imported
    from `applications`, which states that nothing depends on it -- and that
    has to stay true.
    """

    model_config = ConfigDict(from_attributes=True)

    full_name: str | None = None
    phone: str | None = None
    email: str | None = None


class InterestedLearnerOut(BaseModel):
    """One interest, as the provider sees it.

    **There is no candidate card here, and that is deliberate.** An employer's
    applicant carries `candidate_card()` because a vacancy has required
    standards to score against; a course has none, and inventing a second
    scorer to fill this screen is exactly what ADR-037 forbids. So a provider
    is told who wants the course, how to reach them, and where they are --
    never how good they are, nor which vacancy the gap came from, which would
    name a third party and the learner's job-search intent.
    """

    interest_id: uuid.UUID
    status: InterestStatus
    registered_at: datetime
    message: str | None = None
    # Where they are, so an offline batch can be scheduled somewhere. Present
    # while live, like the contact -- a withdrawn row keeps the fact and loses
    # the person entirely.
    location_state: str | None = None
    location_district: str | None = None
    # None once withdrawn: the provider keeps the fact and loses the person.
    contact: LearnerContactOut | None = None


class InterestedLearnerPage(BaseModel):
    course: CourseRef
    items: list[InterestedLearnerOut] = Field(default_factory=list)
    total: int


class CourseInterestCount(BaseModel):
    """How many learners want one course, for the provider's own list."""

    course_slug: str
    course_title: str
    live: int
    total: int


class ProviderStatusIn(BaseModel):
    """What a provider may set. `registered` and `withdrawn` are the learner's."""

    status: ProviderStatus
