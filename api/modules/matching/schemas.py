"""What a match looks like over the wire.

The reason structure is the payload, not decoration on it. Every field the
interface shows comes from the scorer, so the explanation cannot drift from the
score (ADR-036).
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from api.modules.skills.schemas import NsqfLevel


class MatchedSkillOut(BaseModel):
    nos_code: str | None = None
    name_en: str
    importance: int
    is_mandatory: bool
    evidence: str
    proficiency: int


class MissingSkillOut(BaseModel):
    skill_id: uuid.UUID
    nos_code: str | None = None
    name_en: str
    importance: int
    is_mandatory: bool
    nsqf_level: NsqfLevel | None = None


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title_en: str
    title_hi: str | None = None
    location_state: str | None = None
    location_district: str | None = None
    employment_type: str
    nsqf_level_min: NsqfLevel | None = None
    salary_min_inr: int | None = None
    salary_max_inr: int | None = None


class MatchOut(BaseModel):
    """A ranked job with the whole of why."""

    job: JobSummary
    score: int
    coverage: float
    matched: list[MatchedSkillOut] = Field(default_factory=list)
    missing: list[MissingSkillOut] = Field(default_factory=list)
    missing_mandatory: int = 0
    level_shortfall: NsqfLevel | None = None
    # True when a missing mandatory standard held the score down. Surfaced so
    # the interface can say *why* a strong-looking match scored where it did.
    capped_by_mandatory: bool = False


class MatchPage(BaseModel):
    items: list[MatchOut]
    total: int
    # Zero declared skills is not an empty result set, it is a different state,
    # and the interface says so rather than showing "no matches found".
    has_skills: bool


class CourseSuggestionOut(BaseModel):
    slug: str
    title_en: str
    title_hi: str | None = None
    mode: str
    duration_hours: int | None = None
    fee_inr: int | None = None
    closes: list[str]
    closes_count: int
    gap_size: int
    covers_mandatory: int


class EntryRouteOut(BaseModel):
    qp_code: str
    qp_name: str
    routes_total: int
    education_options: list[str]
    lowest_experience_years: float | None = None


class MatchDetail(MatchOut):
    """One match, with what to do about the gap."""

    courses: list[CourseSuggestionOut] = Field(default_factory=list)
    entry: EntryRouteOut | None = None
