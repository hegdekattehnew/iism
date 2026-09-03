import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.modules.identity import TenantOut
from api.modules.skills.schemas import SkillOut

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


class JobSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: SkillOut
    importance: int
    is_mandatory: bool


class CourseSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill: SkillOut
    level_taught: int | None = None


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
    nsqf_level_min: int | None = None
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
    nsqf_level: int | None = None
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
