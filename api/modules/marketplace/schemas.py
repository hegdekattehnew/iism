import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.modules.identity import TenantOut
from api.modules.skills.schemas import NsqfLevel, NsqfLevelIn, SkillOut

EmploymentType = Literal["full_time", "part_time", "contract", "apprenticeship"]
CourseMode = Literal["online", "offline", "hybrid"]
CourseLanguage = Literal["en", "hi", "both"]
Status = Literal["draft", "published"]
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
    title_en: str
    title_hi: str | None = None
    description_en: str | None = None
    description_hi: str | None = None
    location_state: str | None = None
    location_district: str | None = None
    employment_type: EmploymentType
    experience_min_years: int
    experience_max_years: int | None = None
    salary_min_inr: int | None = None
    salary_max_inr: int | None = None
    nsqf_level_min: NsqfLevel | None = None
    tenant: TenantOut


class JobDetail(JobOut):
    skills: list[JobSkillOut] = Field(default_factory=list)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title_en: str
    title_hi: str | None = None
    description_en: str | None = None
    description_hi: str | None = None
    mode: CourseMode
    language: CourseLanguage
    duration_hours: int | None = None
    fee_inr: int | None = None
    nsqf_level: NsqfLevel | None = None
    qualification_pack_code: str | None = None
    tenant: TenantOut


class CourseDetail(CourseOut):
    skills: list[CourseSkillOut] = Field(default_factory=list)


class JobPage(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int


class CoursePage(BaseModel):
    items: list[CourseOut]
    total: int
    limit: int
    offset: int


class MarketplaceCounts(BaseModel):
    jobs: int
    courses: int


# ------------------------------------------------------------ candidate profile


class CandidateSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: SkillOut
    proficiency: int
    source: SkillSource


class CandidateProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    headline: str | None = None
    location_state: str | None = None
    location_district: str | None = None
    years_experience: int
    education_level: EducationLevel | None = None
    skills: list[CandidateSkillOut] = Field(default_factory=list)


class CandidateProfileUpdate(BaseModel):
    headline: str | None = Field(default=None, max_length=160)
    location_state: str | None = Field(default=None, max_length=80)
    location_district: str | None = Field(default=None, max_length=80)
    years_experience: int = Field(default=0, ge=0, le=60)
    education_level: EducationLevel | None = None


class CandidateSkillAdd(BaseModel):
    skill_slug: str
    proficiency: int = Field(default=3, ge=1, le=5)


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


class CandidateProfileUpdateFull(BaseModel):
    """Every field optional: sections save independently, so a partial payload
    must not blank out fields the user was not editing."""

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

    @model_validator(mode="after")
    def _check_salary_range(self) -> "CandidateProfileUpdateFull":
        lo, hi = self.expected_salary_min_inr, self.expected_salary_max_inr
        if lo is not None and hi is not None and hi < lo:
            raise ValueError("expected_salary_max_inr cannot be below expected_salary_min_inr")
        return self


class CorpusStatsOut(BaseModel):
    """What the platform holds, counted live. Backs the landing page."""

    model_config = ConfigDict(from_attributes=True)

    standards: int
    qualifications: int
    criteria: int
    awarding_bodies: int
    sectors: int
    states: int
    districts: int
    entry_routes: int
    jobs: int
    courses: int
