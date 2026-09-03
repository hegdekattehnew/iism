import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkillType = Literal["technical", "core", "generic"]
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
    nsqf_level: int | None = None


class SkillDetail(SkillOut):
    aliases: list[AliasOut] = Field(default_factory=list)


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
