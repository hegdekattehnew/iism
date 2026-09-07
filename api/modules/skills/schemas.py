import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

SkillType = Literal["technical", "core", "generic"]

# NSQF levels run 1-10 and the national corpus uses half steps: 2.5, 3.5, 4.5,
# 5.5 and 6.5 all occur, across 1,369 qualifications and 8,055 units. Carried as
# float, not Decimal, so the generated TypeScript client sees `number` rather
# than a string union; every half step is exact in binary floating point.
#
# Deliberately unconstrained on the way OUT. An output schema that re-validates
# what the database already holds converts a data oddity into a 500 for the
# whole response -- which is precisely the bug this type was introduced to fix.
NsqfLevel = float

# Constrained on the way IN, where rejecting bad input is the point.
NsqfLevelIn = Annotated[float, Field(ge=1, le=10, multiple_of=0.5)]
AliasScript = Literal["latin", "devanagari", "transliteration"]


class AliasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    surface_form: str
    script: AliasScript


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name_en: str
    name_hi: str | None = None
    description_en: str | None = None
    description_hi: str | None = None
    skill_type: SkillType
    nsqf_level: NsqfLevel | None = None
    qp_count: int = 0
    # Promoted from SkillDetail. An employer picking a required standard needs
    # the code -- `HSS/N5134` is what an assessor, a certificate and a
    # qualification pack all say -- and a picker showing only a name asks them
    # to trust a string match they cannot check.
    nos_code: str | None = None


class SkillDetail(SkillOut):
    aliases: list[AliasOut] = Field(default_factory=list)
    # Provenance. `nsqf` is a real National Occupational Standard and the only
    # kind carrying a code an assessor would recognise. `legacy` is one of the
    # 52 hand-written skills, superseded by the standard it maps to but kept
    # because profiles still reference it.
    #
    # A plain string, not a Literal: adding `legacy` to the enum turned this
    # endpoint into a 500 for every retired row before the value was listed
    # here, which is the "output schemas stay permissive" rule in CLAUDE.md
    # earning its keep again.
    source: str = "curated"
    nos_version: str | None = None
    nos_type: str | None = None


class SkillSearchHit(SkillOut):
    """A search result plus why it matched — the UI shows the matched alias so a
    transliterated hit does not look like a mistake."""

    matched_on: str | None = None
    match_kind: Literal["exact", "prefix", "alias", "text"] = "text"


class SkillPage(BaseModel):
    items: list[SkillOut]
    total: int
    limit: int
    offset: int


class SkillCount(BaseModel):
    count: int


class LevelFacet(BaseModel):
    level: NsqfLevel
    count: int


class TypeFacet(BaseModel):
    skill_type: SkillType
    count: int


class SkillFacets(BaseModel):
    """The filter options that actually exist in the data, with their counts.

    Served rather than hardcoded in the client for one concrete reason: the
    taxonomy holds 8,055 skills at half-levels, 6,532 of them at 4.5 alone. A
    dropdown listing 1-10 hides 38% of the corpus behind options that silently
    do not exist, and no test catches a filter that returns a correct empty page.
    """

    total: int
    levels: list[LevelFacet]
    types: list[TypeFacet]
    unlevelled: int


QpRequirement = Literal["compulsory", "elective", "optional"]


class QualificationRefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    qp_code: str
    version: str
    slug: str
    name_en: str
    name_hi: str | None = None
    job_role_en: str | None = None
    nsqf_level: NsqfLevel | None = None
    # How the qualification uses this unit. An elective sits inside a named
    # "choose from" group, and dropping that distinction would present an option
    # as a requirement.
    requirement: QpRequirement
    group_name: str | None = None
    sector_name_en: str | None = None
    sector_slug: str | None = None


class SkillQualifications(BaseModel):
    items: list[QualificationRefOut]
    total: int


class CriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pc_ref: str | None = None
    description_en: str
    description_hi: str | None = None
    total_marks: float | None = None


class PerformanceElementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name_en: str
    name_hi: str | None = None
    total_marks: float | None = None
    criteria: list[CriterionOut] = Field(default_factory=list)


class SkillRequirements(BaseModel):
    """The substance of a standard, as against its title."""

    elements: list[PerformanceElementOut]
    criteria_count: int
    knowledge: list[str]
    generic_skills: list[str]
