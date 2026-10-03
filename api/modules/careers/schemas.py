"""Wire shapes for the career ladder. Output schemas stay permissive."""

from typing import Literal

from pydantic import BaseModel, Field

from api.modules.careers.service import CareerLadder, CareerStep
from api.modules.matching import CourseSuggestionOut, EntryRouteOut, MissingSkillOut
from api.modules.skills import NsqfLevel, RoleRef


class RoleRefOut(BaseModel):
    slug: str
    qp_code: str
    job_role: str
    nsqf_level: NsqfLevel
    sector_name: str | None = None

    @classmethod
    def from_ref(cls, ref: RoleRef) -> "RoleRefOut":
        return cls(
            slug=ref.slug,
            qp_code=ref.qp_code,
            job_role=ref.job_role,
            nsqf_level=ref.nsqf_level,
            sector_name=ref.sector_name,
        )


class StepBasisOut(BaseModel):
    """Why this role is offered, so a reader can judge it rather than trust it."""

    shared_standards: int
    compulsory_count: int
    same_occupation: bool
    shared_nco: bool


class CareerStepOut(BaseModel):
    role: RoleRefOut
    basis: StepBasisOut
    variants: int
    score: int
    coverage: float
    missing: list[MissingSkillOut] = Field(default_factory=list)
    missing_mandatory: int
    level_shortfall: float | None = None
    experience_shortfall: int | None = None
    courses: list[CourseSuggestionOut] = Field(default_factory=list)
    entry: EntryRouteOut | None = None

    @classmethod
    def from_step(cls, s: CareerStep) -> "CareerStepOut":
        r = s.fit.result
        entry = s.fit.entry
        return cls(
            role=RoleRefOut(
                slug=s.step.slug,
                qp_code=s.step.qp_code,
                job_role=s.step.job_role,
                nsqf_level=s.step.nsqf_level,
                sector_name=s.step.sector_name,
            ),
            basis=StepBasisOut(
                shared_standards=s.step.shared_standards,
                compulsory_count=s.step.compulsory_count,
                same_occupation=s.step.same_occupation,
                shared_nco=s.step.shared_nco,
            ),
            variants=s.step.variants,
            score=r.score,
            coverage=round(r.coverage, 4),
            missing=[MissingSkillOut.from_missing(m) for m in r.missing],
            missing_mandatory=r.missing_mandatory,
            level_shortfall=float(r.level_shortfall) if r.level_shortfall is not None else None,
            experience_shortfall=r.experience_shortfall,
            courses=[CourseSuggestionOut.from_suggestion(c) for c in s.courses],
            entry=(
                EntryRouteOut(
                    qp_code=entry.qp_code,
                    qp_name=entry.qp_name,
                    routes_total=entry.routes_total,
                    education_options=entry.education_options,
                    lowest_experience_years=(
                        float(entry.lowest_experience_years)
                        if entry.lowest_experience_years is not None
                        else None
                    ),
                )
                if entry is not None
                else None
            ),
        )


class CareerLadderOut(BaseModel):
    anchor: RoleRefOut | None = None
    """Where the ladder starts. `None` means the person has to choose."""
    anchor_source: Literal["chosen", "guessed", "none"]
    needs_choice: bool
    has_skills: bool
    steps: list[CareerStepOut] = Field(default_factory=list)

    @classmethod
    def from_ladder(cls, c: CareerLadder) -> "CareerLadderOut":
        return cls(
            anchor=RoleRefOut.from_ref(c.ladder.anchor) if c.ladder is not None else None,
            anchor_source=c.source,
            needs_choice=c.needs_choice,
            has_skills=c.has_skills,
            steps=[CareerStepOut.from_step(s) for s in c.steps],
        )
