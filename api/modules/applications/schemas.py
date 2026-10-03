import uuid
from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from api.modules.applications.models import (
    APPLICATION_STATUSES,
    EMPLOYER_STATUSES,
    REVIEW_SUBJECT_ROLES,
)
from api.modules.identity import TenantOut
from api.modules.matching import CandidateCardOut
from api.modules.matching.schemas import CourseSuggestionOut, JobPoolOut, MissingSkillOut
from api.modules.skills.schemas import NsqfLevel

# Closed on the way out so the generated TypeScript client types a status as a
# union rather than `string`; `tests/test_enumerations.py` holds it to the CHECK.
# `completed`/`no_show` (Sprint 37, Epic B8) are a gig engagement's outcome.
ApplicationStatus = Literal[
    "applied", "withdrawn", "shortlisted", "rejected", "hired", "completed", "no_show"
]
EmployerStatus = Literal["shortlisted", "rejected", "hired", "completed", "no_show"]
ReviewSubjectRole = Literal["poster", "worker"]

# The unions above and the tuples the CHECK is generated from must agree. A
# closed union on an output model is a latent 500 the moment the database holds
# a value it does not list -- twice already in this project.
assert set(get_args(ApplicationStatus)) == set(APPLICATION_STATUSES)  # noqa: S101
assert set(get_args(EmployerStatus)) == set(EMPLOYER_STATUSES)  # noqa: S101
assert set(get_args(ReviewSubjectRole)) == set(REVIEW_SUBJECT_ROLES)  # noqa: S101


class JobRef(BaseModel):
    """Enough of a vacancy to recognise it in a list of your own applications."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
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


class ReputationOut(BaseModel):
    """An average rating and how many it rests on. Absent, not zero, when
    nobody has rated yet (`reputation.py`)."""

    model_config = ConfigDict(from_attributes=True)

    average: float
    count: int


class PosterRatingOut(BaseModel):
    """What a vacancy's page shows about whoever posted it. An object rather
    than a bare `null`, which a client cannot tell from a failed request."""

    rating: ReputationOut | None = None


class ApplicationOut(BaseModel):
    """The candidate's own view of an application."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job: JobRef
    status: ApplicationStatus
    message: str | None = None
    applied_at: datetime
    updated_at: datetime
    # Has this candidate already rated the poster. Without it the rating form
    # could not tell whether to show itself, and the API answers a second
    # review with a 409.
    reviewed: bool = False


class ApplicationGapOut(BaseModel):
    """What one of the candidate's own applications was missing ("Why not me").

    The same shapes a match card uses -- `MissingSkillOut` and
    `CourseSuggestionOut` come from `matching` -- so a rejection and a match name
    the gap identically. Never put in a notification payload: the outbox and an
    email can reach a shared address.
    """

    application_id: uuid.UUID
    job: JobRef
    status: ApplicationStatus
    score: int
    coverage: float
    missing: list[MissingSkillOut] = Field(default_factory=list)
    missing_mandatory: int
    level_shortfall: float | None = None
    capped_by_mandatory: bool
    courses: list[CourseSuggestionOut] = Field(default_factory=list)


class SavedJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job: JobRef
    saved_at: datetime


class ContactOut(BaseModel):
    """The disclosure itself.

    Present only while an application is live. This is the **only** payload in
    the product that names a candidate to an employer, and it sits *beside* the
    de-identified card rather than inside it, so ADR-037's invariant stays a
    property of `candidate_card()` and this stays the one exception.
    """

    model_config = ConfigDict(from_attributes=True)

    full_name: str | None = None
    phone: str | None = None
    email: str | None = None


class ApplicantOut(BaseModel):
    """One application, as the employer sees it."""

    application_id: uuid.UUID
    status: ApplicationStatus
    applied_at: datetime
    message: str | None = None
    # Exactly what the ranked pool shows, built by the same function.
    candidate: CandidateCardOut
    # None once withdrawn: the employer keeps the fact and loses the person.
    contact: ContactOut | None = None
    # Has the employer already rated this worker (see `ApplicationOut.reviewed`).
    reviewed: bool = False


class ApplicantPage(BaseModel):
    job: JobRef
    items: list[ApplicantOut] = Field(default_factory=list)
    total: int


class StatusIn(BaseModel):
    """What an employer may set. `applied` and `withdrawn` are the candidate's."""

    status: EmployerStatus


class ReviewIn(BaseModel):
    """One direction of a completed gig engagement's rating (Sprint 37, Epic
    B8). `subject_role` is never accepted here -- it is fixed by which of the
    two routes a caller reaches, never a value the caller states."""

    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(None, max_length=1_000)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_role: ReviewSubjectRole
    rating: int
    comment: str | None = None
    created_at: datetime


class EmployerDashboardOut(BaseModel):
    """An employer's landing numbers (Sprint 39, BL-10.2)."""

    model_config = ConfigDict(from_attributes=True)

    posted_jobs: int
    open_jobs: int
    applied: int
    shortlisted: int
    hired: int
    # How workers rated this organisation; absent until somebody has.
    rating: ReputationOut | None = None
    # The per-job breakdown behind the three counts above (Sprint 40) -- the
    # same `JobPoolOut` shape the employer console already returns, imported
    # rather than restated, so the two can never describe a pool differently.
    jobs: list[JobPoolOut] = Field(default_factory=list)


class TopMatchOut(BaseModel):
    """One of a candidate's best-scoring jobs, enough to draw a ranked bar and
    reuse `CoverageBar`/`LevelScale` for its drilldown (Sprint 40)."""

    job_slug: str
    job_title: str
    score: int
    coverage: float
    missing_mandatory: int
    capped_by_mandatory: bool
    nsqf_level_min: NsqfLevel | None = None
    level_shortfall: NsqfLevel | None = None


class CandidateDashboardOut(BaseModel):
    """A candidate's landing numbers (Sprint 39, BL-10.1)."""

    model_config = ConfigDict(from_attributes=True)

    match_count: int
    best_score: int | None = None
    applied: int
    shortlisted: int
    hired: int
    profile_completeness: int
    # How employers rated this candidate's finished gigs; absent until somebody has.
    rating: ReputationOut | None = None
    # The `scored` list `match_jobs()` already returns, sliced to its top few
    # (Sprint 40) -- zero new queries, since `dashboard()` already calls it.
    top_matches: list[TopMatchOut] = Field(default_factory=list)
