import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from api.core.clock import today_ist
from api.modules.identity import TenantOut
from api.modules.skills.schemas import NsqfLevel, NsqfLevelIn, SkillOut

EmploymentType = Literal["full_time", "part_time", "contract", "apprenticeship", "gig"]
CourseMode = Literal["online", "offline", "hybrid"]
CourseLanguage = Literal["en", "hi", "both"]
Status = Literal["draft", "published"]
JobSort = Literal["title", "newest"]
SkillSource = Literal["self_declared", "inferred", "assessed", "certified"]
EducationLevel = Literal[
    "none",
    "primary",
    "secondary",
    "higher_secondary",
    "iti",
    "diploma",
    "graduate",
    "postgraduate",
]
Gender = Literal["female", "male", "other", "prefer_not_to_say"]
LanguageProficiency = Literal["basic", "conversational", "fluent", "native"]
NoticePeriod = Literal["immediate", "within_15_days", "within_30_days", "over_30_days"]


class JobSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: SkillOut
    importance: int
    is_mandatory: bool


class CourseSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: SkillOut
    level_taught: NsqfLevel | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    # Bounded on the way in, not in the column (free prose stays `Text`): the
    # cap is about what one request may make us store and render, not the data.
    description: str | None = Field(None, max_length=10_000)
    location_state: str | None = None
    location_district: str | None = None
    employment_type: EmploymentType
    experience_min_years: int
    experience_max_years: int | None = None
    salary_min_inr: int | None = None
    salary_max_inr: int | None = None
    nsqf_level_min: NsqfLevel | None = None
    tenant: TenantOut

    # The lifecycle, on the public payload because the public page renders it.
    # `is_open` rather than the raw timestamps as the thing clients branch on:
    # it is one question with one answer, and three components each deriving
    # "published and not closed" is three chances to derive it differently.
    is_open: bool = True
    positions: int = 1
    closes_at: datetime | None = None
    closed_at: datetime | None = None
    # When it last went live (Sprint 74, ADR-084). Null for a vacancy published before the column
    # existed, and a client renders nothing for null: `created_at` would be the draft's date.
    published_at: datetime | None = None
    # Permissive `str`, not a Literal: this is an output model, and a closed
    # reason the schema has not heard of should render oddly rather than 500
    # the whole listing. The CHECK on the column is what keeps it closed.
    close_reason: str | None = None


class JobCloseIn(BaseModel):
    """Why a vacancy is closing. `expired` is absent: that one is the worker's,
    written when a closing date passes, and an employer claiming it would make
    the reason a vacancy closed untrue."""

    reason: Literal["filled", "withdrawn"] = "filled"


class JobDetail(JobOut):
    skills: list[JobSkillOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# What an employer sends (ADR-039). Constraints live on the way in; the *Out
# models above stay permissive, because a constraint on a response model turns
# one odd row into a 500 for the whole page.
# ---------------------------------------------------------------------------


class JobSkillIn(BaseModel):
    """One required standard, with the two facts that make a match scoreable."""

    skill_slug: str
    importance: int = Field(3, ge=1, le=5)
    is_mandatory: bool = False


class JobIn(BaseModel):
    """A vacancy as its employer describes it.

    No `status` field: publishing is an explicit action on its own endpoint, not
    something a form can do by setting a string. `Job.status` defaults to
    `published` at the model level, so the service must set `draft` by hand --
    a footgun this schema deliberately keeps out of reach.
    """

    title: str = Field(min_length=3, max_length=200)
    # Bounded on the way in, not in the column (free prose stays `Text`): the
    # cap is about what one request may make us store and render, not the data.
    description: str | None = Field(None, max_length=10_000)
    location_state: str | None = Field(None, max_length=120)
    location_district: str | None = Field(None, max_length=120)
    employment_type: EmploymentType = "full_time"
    experience_min_years: int = Field(0, ge=0, le=60)
    experience_max_years: int | None = Field(None, ge=0, le=60)
    salary_min_inr: int | None = Field(None, ge=0)
    salary_max_inr: int | None = Field(None, ge=0)
    nsqf_level_min: NsqfLevelIn | None = None
    # How many people are being hired. Constrained here, on the way in, and by
    # `ck_jobs_positions` in the database -- a vacancy for zero people would
    # close the moment it was published.
    positions: Annotated[int, Field(ge=1, le=999)] = 1
    # Optional, and in the future. A closing date already past would be closed
    # by the worker within the hour, so accepting one is accepting a vacancy
    # that vanishes for no visible reason.
    closes_at: datetime | None = None
    skills: list[JobSkillIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _ranges_are_the_right_way_round(self) -> "JobIn":
        if (
            self.experience_max_years is not None
            and self.experience_max_years < self.experience_min_years
        ):
            raise ValueError("experience_max_years must not be below experience_min_years")
        if (
            self.salary_min_inr is not None
            and self.salary_max_inr is not None
            and self.salary_max_inr < self.salary_min_inr
        ):
            raise ValueError("salary_max_inr must not be below salary_min_inr")
        return self

    @model_validator(mode="after")
    def _a_gig_has_an_end(self) -> "JobIn":
        """A temporary job assignment without an end date is not one (Sprint
        37, Epic B8). The other half of this invariant -- a gig also needs a
        resolvable place, not "somewhere in India" -- is DB-dependent
        (`resolve_location` is async) and lives in `publishing.py` instead,
        after location resolution runs.
        """
        if self.employment_type == "gig" and self.closes_at is None:
            raise ValueError("A gig posting needs closes_at -- a shift with no end is not a gig")
        return self


class OrgJobOut(JobDetail):
    """An employer's view of their own listing, drafts included.

    Every public listing query hard-filters `status == 'published'`, so a draft
    is unreachable anywhere else in the API. `status` is exposed here because
    this is the one place someone needs to know it.
    """

    status: Status
    updated_at: datetime
    # Set when an operator removed it (Sprint 59): the owner is told when and why, and the publish
    # control says so instead of failing.
    taken_down_at: datetime | None = None
    takedown_reason: str | None = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    # Bounded on the way in, not in the column (free prose stays `Text`): the
    # cap is about what one request may make us store and render, not the data.
    description: str | None = Field(None, max_length=10_000)
    mode: CourseMode
    language: CourseLanguage
    duration_hours: int | None = None
    fee_inr: int | None = None
    nsqf_level: NsqfLevel | None = None
    qualification_pack_code: str | None = None
    # What that code stands for, read when it is shown (Sprint 75, BL-12.8), never stored: the
    # qualification's own job-role name and what it is worth. A statement the **provider** made,
    # so the page says so. `None` when nothing is linked, the pack has gone, or its credits are
    # unknown, zero or not a number.
    qualification_name: str | None = None
    qualification_credits: float | None = None
    # Where, when and how many (Sprint 58, BL-14.5). All optional: a course published before this
    # has no stated place, and the screen says so rather than guessing.
    location_state: str | None = None
    location_district: str | None = None
    starts_on: date | None = None
    seats: int | None = None
    tenant: TenantOut

    @computed_field  # type: ignore[prop-decorator]
    @property
    def started(self) -> bool:
        """Derived from the date, never stored: a stored flag is wrong the morning after."""
        return self.starts_on is not None and self.starts_on < today_ist()


class CourseDetail(CourseOut):
    skills: list[CourseSkillOut] = Field(default_factory=list)
    # Places left: `seats` less the learners the provider has marked enrolled. Derived at read
    # time (`service.seats_left_for`), `None` when the provider gave no seat count.
    seats_left: int | None = None


class ProviderSectorOut(BaseModel):
    """A sector an organisation trains in, with how many of its published courses are in it."""

    name: str
    courses: int


class ProviderPublicOut(BaseModel):
    """A training organisation's public page (Sprint 94, ADR-102).

    **Not `TenantOut`**, which is embedded in every vacancy and course: the claims an organisation
    makes about itself (`affiliations`, `year_established`, `teaching_languages`) are shown on its
    own page and nowhere else, and `contact_email` is on neither. `sectors` is derived from its
    published courses at read time and never stored.
    """

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    city: str | None = None
    description: str | None = None
    website: str | None = None
    logo_url: str | None = None
    is_verified: bool = False
    publishes_courses: bool = False
    delivers_training: bool = False
    year_established: int | None = None
    affiliations: str | None = None
    teaching_languages: str | None = None
    sectors: list[ProviderSectorOut] = Field(default_factory=list)
    courses: list["CourseOut"] = Field(default_factory=list)
    courses_total: int = 0


class CourseSkillIn(BaseModel):
    """One standard a course teaches, and how far it takes the learner.

    Deliberately unlike `JobSkillIn`. A job link carries importance and a
    mandatory flag because a match is scored against them; a course link carries
    only the level it teaches to, because what matters is whether it closes a
    gap and how far.
    """

    skill_slug: str
    level_taught: NsqfLevelIn | None = None


class CourseIn(BaseModel):
    """A course as its provider describes it.

    No `status`, for the same reason `JobIn` has none: publishing is an explicit
    action on its own endpoint, not something a form can do by setting a string.
    """

    title: str = Field(min_length=3, max_length=200)
    # Bounded on the way in, not in the column (free prose stays `Text`): the
    # cap is about what one request may make us store and render, not the data.
    description: str | None = Field(None, max_length=10_000)
    mode: CourseMode = "offline"
    language: CourseLanguage = "both"
    duration_hours: int | None = Field(None, ge=1, le=10_000)
    fee_inr: int | None = Field(None, ge=0)
    nsqf_level: NsqfLevelIn | None = None
    # The qualification this course counts toward, as its provider says (Sprint 75, BL-12.8): a
    # code from role search. Checked against the current packs on write; blank is none.
    qualification_pack_code: str | None = Field(None, max_length=60)
    location_state: str | None = Field(None, max_length=120)
    location_district: str | None = Field(None, max_length=120)
    starts_on: date | None = None
    seats: int | None = Field(None, ge=1, le=100_000)
    skills: list[CourseSkillIn] = Field(default_factory=list, max_length=50)

    @field_validator("qualification_pack_code")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class OrgCourseOut(CourseDetail):
    """A provider's view of their own listing, drafts included."""

    status: Status
    updated_at: datetime
    taken_down_at: datetime | None = None
    takedown_reason: str | None = None


class JobPage(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int


class JobStateOut(BaseModel):
    """A state that has at least one open vacancy, and how many (Sprint 69, UI-06).

    The state filter used to be read off whatever page of vacancies was loaded, which is wrong
    the moment the list pages. It is a fact about the catalogue, so the API says it.
    """

    name: str
    count: int


class CoursePage(BaseModel):
    items: list[CourseOut]
    total: int
    limit: int
    offset: int


class MarketplaceCounts(BaseModel):
    """The homepage panels' figures.

    Jobs is two numbers and courses is one, and the asymmetry is the honest
    shape rather than an oversight: a course has no closed state -- `status`
    is its whole lifecycle -- so "published" and "still on offer" are the same
    question there and two different ones for a vacancy.
    """

    jobs_posted: int
    jobs_open: int
    courses: int


# ------------------------------------------------------------ candidate profile


class CandidateSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: SkillOut
    proficiency: int
    source: SkillSource


class CandidateSkillAdd(BaseModel):
    skill_slug: str
    proficiency: int = Field(default=3, ge=1, le=5)


class CandidateSkillsBulkAdd(BaseModel):
    """Several standards at once -- the ones ticked from a suggested role.

    `preferred_role_title` is the role they came from, recorded as a preferred
    role when given. Bounded at the profile's own cap: a longer list could
    never be accepted, so it is refused before anything is looked up.
    """

    items: list[CandidateSkillAdd] = Field(min_length=1, max_length=60)
    preferred_role_title: str | None = Field(default=None, max_length=120)


# ------------------------------------------------- profile child collections


class ExperienceIn(BaseModel):
    employer_name: str = Field(min_length=1, max_length=120)
    role_title: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    started_on: date
    ended_on: date | None = None
    is_current: bool = False
    description: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check_dates(self) -> "ExperienceIn":
        if self.is_current:
            # A role you still hold cannot have an end date; silently keeping
            # one would make duration calculations wrong later.
            self.ended_on = None
        elif self.ended_on and self.ended_on < self.started_on:
            raise ValueError("ended_on cannot be before started_on")
        return self


class ExperienceOut(ExperienceIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class EducationIn(BaseModel):
    qualification: str = Field(min_length=1, max_length=160)
    institution: str | None = Field(default=None, max_length=160)
    specialisation: str | None = Field(default=None, max_length=120)
    education_level: EducationLevel | None = None
    year_completed: int | None = Field(default=None, ge=1950, le=2100)
    is_pursuing: bool = False


class EducationOut(EducationIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class CertificationIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    issuing_body: str | None = Field(default=None, max_length=160)
    credential_id: str | None = Field(default=None, max_length=80)
    issued_on: date | None = None
    expires_on: date | None = None
    nsqf_level: NsqfLevelIn | None = None
    skill_slug: str | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> "CertificationIn":
        if self.issued_on and self.expires_on and self.expires_on < self.issued_on:
            raise ValueError("expires_on cannot be before issued_on")
        return self


class CertificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    issuing_body: str | None = None
    credential_id: str | None = None
    issued_on: date | None = None
    expires_on: date | None = None
    nsqf_level: NsqfLevel | None = None
    skill: SkillOut | None = None


class LanguageIn(BaseModel):
    language: str = Field(min_length=2, max_length=40)
    proficiency: LanguageProficiency = "conversational"
    can_read: bool = True
    can_write: bool = True


class LanguageOut(LanguageIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class PreferredRoleIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class PreferredRoleOut(PreferredRoleIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class PreferredLocationIn(BaseModel):
    state: str = Field(min_length=1, max_length=80)
    district: str | None = Field(default=None, max_length=80)


class PreferredLocationOut(PreferredLocationIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


# --------------------------------------------------------- the full profile


class ProfileCompleteness(BaseModel):
    """Drives the progress meter and tells the candidate what to do next."""

    percent: int = 0
    missing: list[str] = Field(default_factory=list)


class CandidateProfileFull(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None = None

    headline: str | None = None
    location_state: str | None = None
    location_district: str | None = None
    years_experience: int
    education_level: EducationLevel | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None

    willing_to_relocate: bool = False
    preferred_employment_type: EmploymentType | None = None
    expected_salary_min_inr: int | None = None
    expected_salary_max_inr: int | None = None
    notice_period: NoticePeriod | None = None
    # On by default, and the one thing in this product that sends somebody a
    # message they did not ask for in the moment -- so it is on the profile
    # where they can find it, not buried in an account screen.
    job_alerts_enabled: bool = True
    # The role the person confirmed as the work they do now (Sprint 74, BL-6.5). Theirs to set and
    # to clear; read by the career page only, never by matching or an employer.
    current_role_slug: str | None = None
    onboarding_completed_at: datetime | None = None

    skills: list[CandidateSkillOut] = Field(default_factory=list)
    experiences: list[ExperienceOut] = Field(default_factory=list)
    educations: list[EducationOut] = Field(default_factory=list)
    certifications: list[CertificationOut] = Field(default_factory=list)
    languages: list[LanguageOut] = Field(default_factory=list)
    preferred_roles: list[PreferredRoleOut] = Field(default_factory=list)
    preferred_locations: list[PreferredLocationOut] = Field(default_factory=list)

    # Neither of these is a column: full_name lives on the identity side and
    # completeness is derived. Both are filled in by the route after validation.
    completeness: ProfileCompleteness = Field(default_factory=ProfileCompleteness)


MINIMUM_AGE = 18


def years_between(born: date, today: date) -> int:
    """Whole years from `born` to `today`: the birthday has to have passed this year."""
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


class CandidateProfileUpdateFull(BaseModel):
    """Every field optional: sections save independently, so a partial payload
    must not blank out fields the user was not editing."""

    @field_validator("date_of_birth")
    @classmethod
    def _adult(cls, value: date | None) -> date | None:
        """The privacy notice says 18 and over, and nothing checked it (Sprint 72, ADR-082).

        Refused on write, in words the form can show. Existing profiles are not rewritten; a
        stored date is only looked at when somebody saves one. Whether and how a minor may ever
        use the product is the owner's decision, not this rule's.
        """
        if value is not None and years_between(value, today_ist()) < MINIMUM_AGE:
            raise ValueError(
                f"You must be {MINIMUM_AGE} or over to use this service. "
                "Check the date of birth you entered."
            )
        return value

    full_name: str | None = Field(default=None, max_length=120)
    headline: str | None = Field(default=None, max_length=160)
    location_state: str | None = Field(default=None, max_length=80)
    location_district: str | None = Field(default=None, max_length=80)
    years_experience: int | None = Field(default=None, ge=0, le=60)
    education_level: EducationLevel | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    willing_to_relocate: bool | None = None
    preferred_employment_type: EmploymentType | None = None
    expected_salary_min_inr: int | None = Field(default=None, ge=0)
    expected_salary_max_inr: int | None = Field(default=None, ge=0)
    notice_period: NoticePeriod | None = None
    job_alerts_enabled: bool | None = None
    # An explicit null clears it. Checked against the taxonomy on write (`update_profile`).
    current_role_slug: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check_salary_range(self) -> "CandidateProfileUpdateFull":
        lo, hi = self.expected_salary_min_inr, self.expected_salary_max_inr
        if lo is not None and hi is not None and hi < lo:
            raise ValueError("expected_salary_max_inr cannot be below expected_salary_min_inr")
        return self


class CorpusStatsOut(BaseModel):
    """What the platform holds and what has been done on it, counted live (landing page)."""

    model_config = ConfigDict(from_attributes=True)

    standards: int
    qualifications: int
    criteria: int
    awarding_bodies: int
    sectors: int
    states: int
    districts: int
    entry_routes: int
    jobs_posted: int
    jobs_open: int
    courses: int
    # Who is here and what they have done (Sprint 50.5). Each broad figure has its narrow
    # sibling (`profiles`/`job_seekers`, `employers`/`employers_hiring`, ...) so the page can
    # name the narrower one underneath when they differ.
    job_seekers: int
    profiles: int
    employers: int
    employers_hiring: int
    providers: int
    providers_with_course: int
    applications: int
    hires: int
    districts_with_vacancy: int
    # True when the figures describe a demonstration database, not real use.
    demo: bool


# ---------------------------------------------------------------------------
# Bulk upload (Sprint 51, ADR-063). Output only: the input is the file itself, sent as
# `text/csv`, so the limits live in `JobIn` / `CourseIn` and the rows are validated by them.
# ---------------------------------------------------------------------------


class BulkStandardOut(BaseModel):
    """A standard a row will require or teach, and whether the row listed it or its role gave it."""

    code: str
    name: str
    origin: Literal["listed", "role"]
    importance: int | None = None
    mandatory: bool | None = None
    level: float | None = None


class BulkRowOut(BaseModel):
    row: int
    status: Literal["ok", "warning", "error", "skip", "update"]
    title: str | None = None
    external_ref: str | None = None
    messages: list[str] = Field(default_factory=list)
    standards: list[BulkStandardOut] = Field(default_factory=list)
    # The slug created (after an apply), the one a skipped row matched, or the one it updates.
    slug: str | None = None
    created: bool = False
    # An update of a published listing: the change is public the moment it is applied.
    live: bool = False
    updated: bool = False


class BulkReportOut(BaseModel):
    kind: Literal["jobs", "courses"]
    applied: bool
    rows: list[BulkRowOut]
    notes: list[str] = Field(default_factory=list)
    ok: int
    warnings: int
    errors: int
    skipped: int
    created: int
    # Rows that change an existing listing (a check: will; after an apply: did), how many of those
    # are published, and how many were applied. Only ever non-zero when `existing=update` was asked.
    updates: int = 0
    updating_live: int = 0
    updated: int = 0
    # Rows this organisation may still create in the rolling 24 hours, and the limit itself.
    daily_limit: int
    remaining_today: int
    # The failed rows as uploaded plus an `error` column: fix them, upload the whole file again.
    errors_csv: str | None = None


class BulkPublishIn(BaseModel):
    slugs: list[str] = Field(min_length=1, max_length=200)


class BulkPublishRowOut(BaseModel):
    slug: str
    published: bool
    message: str | None = None


class BulkPublishOut(BaseModel):
    results: list[BulkPublishRowOut]
    published: int
    refused: int
