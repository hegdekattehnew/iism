import uuid
from datetime import datetime
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from api.modules.matching.schemas import ScarceSkillOut
from api.modules.operations.models import VERIFICATION_DECISIONS
from api.modules.skills import ALIAS_ACTIONS, ALIAS_SOURCES

VerificationDecision = Literal["granted", "revoked"]

# The union and the tuple the CHECK is generated from must agree, for the
# reason `tests/test_enumerations.py` exists: a widened constraint is invisible
# both to autogenerate and to the schema beside it.
assert set(get_args(VerificationDecision)) == set(VERIFICATION_DECISIONS)  # noqa: S101

# What the verification queue can be narrowed to (Sprint 95): an organisation's kind, or a centre.
ReviewKind = Literal["employer", "course_provider", "training_centre"]

AliasSource = Literal["seed", "operator"]
AliasAction = Literal["added", "retired"]
assert set(get_args(AliasSource)) == set(ALIAS_SOURCES)  # noqa: S101
assert set(get_args(AliasAction)) == set(ALIAS_ACTIONS)  # noqa: S101


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
    # A centre only (Sprint 95): the organisation behind it and the place an operator is checking.
    parent_name: str | None = None
    parent_slug: str | None = None
    address: str | None = None
    district: str | None = None
    state: str | None = None


class OrganisationQueue(BaseModel):
    """The verification queue with its true size (Sprint 69, UI-17).

    `total` is every organisation waiting, counted in the database. `len(items)` is only the page:
    the screen used to print that as the queue's size, and the cap of 100 made it read "100
    waiting" beside an overview that said 162.
    """

    items: list[UnverifiedOrganisation]
    total: int
    limit: int
    offset: int


class PlatformDashboardOut(BaseModel):
    """An operator's landing numbers (Sprint 39, BL-10.4)."""

    model_config = ConfigDict(from_attributes=True)

    unverified_organisations: int
    unverified_certifications: int
    organisations: int
    candidates: int
    published_jobs: int
    published_courses: int
    # Sprint 40: the same `ScarceSkillOut` shape the employer console and the
    # provider-facing market router already return, imported rather than
    # restated.
    scarce_skills: list[ScarceSkillOut] = Field(default_factory=list)


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
    # What is being decided about (Sprint 95): an organisation, or a centre's address. A centre also
    # carries whose it is and the address an operator is checking.
    tenant_type: str | None = None
    parent_name: str | None = None
    parent_slug: str | None = None
    address: str | None = None
    district: str | None = None
    state: str | None = None


class UnverifiedCertification(BaseModel):
    """One row of the certification queue (Sprint 35, BL-3.2): enough to
    decide without opening anything else."""

    id: uuid.UUID
    candidate_name: str | None = None
    name: str
    issuing_body: str | None = None
    credential_id: str | None = None
    skill_slug: str
    skill_name: str


class CertificationQueue(BaseModel):
    """The certification queue with its true size, for the reason `OrganisationQueue` has one."""

    items: list[UnverifiedCertification]
    total: int
    limit: int
    offset: int


class CertificationVerifyIn(BaseModel):
    """The evidence for a decision. No `decision` field, unlike organisation
    verification: a certification has no revoke path yet (the candidate's own
    edit/delete controls that row), so there is only ever one direction."""

    note: Annotated[str, Field(min_length=10, max_length=500)]


class VerifiedCertificationOut(BaseModel):
    id: uuid.UUID
    name: str
    skill_slug: str
    verified_at: datetime
    verification_note: str


class ProgrammeReportOut(BaseModel):
    """Outcomes for one government-agency programme (Sprint 33, BL-7.1b)."""

    model_config = ConfigDict(from_attributes=True)

    programme: str
    enrolled: int
    matched: int
    applied: int
    hired: int


class KnownProgrammesOut(BaseModel):
    """Every programme name a candidate is actually enrolled under (Sprint 39,
    BL-10.5) -- a starting point for `programme_report`'s free-text name, not a
    second source of truth for what a "real" programme is."""

    programmes: list[str]


class DistrictBreakdownOut(BaseModel):
    """How many of one programme's enrolled candidates live in one district
    (Sprint 40). `district` is `"Unknown"` for a candidate whose location
    never resolved, never omitted -- the bars still sum to `enrolled`."""

    district: str
    # `null` when one to four live there: not shown (ADR-057), so the bars no longer add up to
    # `enrolled` and are not meant to.
    enrolled: int | None = None
    below_minimum: bool = False


class ProgrammeDistrictsOut(BaseModel):
    """A programme's enrolment, broken down by district (Sprint 40) -- a
    separate, heavier query from `programme_report`'s own four numbers."""

    programme: str
    minimum_cell: int
    districts: list[DistrictBreakdownOut] = Field(default_factory=list)


# ------------------------------------------------------------ district skill gap (Sprint 49)


class DistrictOptionOut(BaseModel):
    """A district with at least one open vacancy, for the picker."""

    id: uuid.UUID
    name: str
    state: str | None = None
    vacancies: int


class DistrictOptionsOut(BaseModel):
    districts: list[DistrictOptionOut] = Field(default_factory=list)


class DistrictGapRowOut(BaseModel):
    """One standard employers in the district ask for.

    `supply` is `null` when one to four residents hold it: a small count of people in a
    place nearly describes them, so it is not shown (`operations.skill_gap`). The
    shortfall is then computed against the largest hidden value and is a minimum.
    """

    nos_code: str | None = None
    name: str
    vacancies: int
    demand: int
    supply: int | None = None
    supply_below_minimum: bool
    shortfall: int
    shortfall_is_minimum: bool


class DistrictSkillGapOut(BaseModel):
    district: DistrictOptionOut
    positions: int
    residents: int | None = None
    residents_below_minimum: bool
    minimum_cell: int
    standards: list[DistrictGapRowOut] = Field(default_factory=list)


# ------------------------------------------------------------ role aliases (Sprint 47)


class RoleAliasIn(BaseModel):
    """A term somebody might type, and the role it should find.

    The limits mirror `skills.alias_admin` (`MIN_KEY_LENGTH`, `MAX_KEY_LENGTH`,
    `MAX_NOTE_LENGTH`) and `web/src/lib/constraints.test.ts` holds the form to them. The
    target is the role's name as the corpus spells it; the screen offers it from role
    search so it is picked, not typed.
    """

    surface_form: str = Field(min_length=2, max_length=80)
    job_role: str = Field(min_length=1, max_length=300)
    note: str | None = Field(None, max_length=300)


class RoleAliasRetireIn(BaseModel):
    note: str | None = Field(None, max_length=300)


class AliasTargetOut(BaseModel):
    """The role an alias would find: the pack that stands for it, as role search names it."""

    job_role: str
    slug: str
    qp_code: str
    nsqf_level: float | None = None
    standards_count: int
    sector_name: str | None = None


class RoleAliasCheckOut(BaseModel):
    """What adding this alias would do, with nothing written."""

    ok: bool
    surface_form: str
    target: AliasTargetOut | None = None
    problems: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    existing: Literal["active", "retired"] | None = None


class RoleAliasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    surface_form: str
    job_role: str
    source: AliasSource
    created_at: datetime


class RoleAliasListOut(BaseModel):
    items: list[RoleAliasOut]
    total: int
    """Every live alias, so the screen can say "showing 100 of 114"."""


class RoleAliasEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: AliasAction
    surface_form: str
    job_role: str
    note: str | None = None
    created_at: datetime


# ---------------------------------------------------------------- agency enrolment (Sprint 61)

EnrolmentStatus = Literal["new", "tag", "already", "error"]


class EnrolmentRowOut(BaseModel):
    """One row of a check or an apply. **Nothing here can be dialled**: the phone is masked and
    the name is its first word. The operator already holds the file."""

    row: int
    status: EnrolmentStatus
    phone: str | None = None
    first_name: str | None = None
    warnings: list[str] = []
    errors: list[str] = []


class EnrolmentReportOut(BaseModel):
    programme: str
    applied: bool
    rows: list[EnrolmentRowOut]
    notes: list[str]
    new: int
    tag: int
    already: int
    errors: int
    # The rows that failed, exactly as uploaded plus an `error` column (formula-safe).
    errors_csv: str | None = None
    batch_id: uuid.UUID | None = None


class EnrolmentBatchOut(BaseModel):
    id: uuid.UUID
    programme: str
    file_name: str | None = None
    # Masked, and `None` once the operator has erased their account.
    operator: str | None = None
    attested_notice_version: str
    attested_at: datetime
    created: int
    tagged: int
    already: int
    errors: int
    created_at: datetime


class EnrolmentBatchesOut(BaseModel):
    batches: list[EnrolmentBatchOut]
