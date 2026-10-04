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
    enrolled: int


class ProgrammeDistrictsOut(BaseModel):
    """A programme's enrolment, broken down by district (Sprint 40) -- a
    separate, heavier query from `programme_report`'s own four numbers."""

    programme: str
    districts: list[DistrictBreakdownOut] = Field(default_factory=list)


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
