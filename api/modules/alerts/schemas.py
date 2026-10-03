"""What an employer sees about offering to train a near-miss candidate (ADR-048).

Built from `matching`'s own shapes so the standard and the courses read the same
here as on the console card and on a candidate's match.
"""

from pydantic import BaseModel, Field

from api.modules.matching.schemas import CourseSuggestionOut, MissingSkillOut


class TrainingOut(BaseModel):
    """The one standard a candidate is missing, and what teaches it."""

    reference: str
    standard: MissingSkillOut
    courses: list[CourseSuggestionOut] = Field(default_factory=list)
    # Whether *this organisation* has already made the offer. Never whether the
    # candidate was told, responded or applied: those are facts about them.
    offered: bool


class SponsorOut(BaseModel):
    """The same answer whether the candidate was notified or not -- an opt-out
    is a fact about the candidate and must not leak through this endpoint."""

    offered: bool = True
