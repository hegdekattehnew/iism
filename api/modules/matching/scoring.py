"""How a candidate is scored against a job (ADR-007, ADR-036).

Deterministic and auditable. **No model is called here and none may be added** —
an employer or a regulator can be told exactly why a score is what it is, and a
golden set can only measure something reproducible.

The output is a *reason structure*, not a number with a sentence attached. The
interface renders that structure, so the explanation cannot drift away from the
score it explains.

Five components, and each uses a signal that already exists rather than one
invented for the purpose:

* **Coverage** — how much of what the job requires the candidate holds,
  weighted by importance. Compared at **concept** level, so a candidate and an
  employer who picked different rows for the same standard still meet.
* **Mandatory** — a missing mandatory standard *caps* the score rather than
  merely reducing it. A job that says a unit is required means it.
* **Evidence** — `candidate_skills.source`. Certified and assessed claims
  outrank self-declared ones, which is what that column was added for in
  Sprint 4.
* **Level** — the candidate's attained level against the job's floor.
* **Eligibility** — `qp_entry_routes`. Not part of the score: a candidate is
  eligible or they are not, and burying that in a weighted average would hide it.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

# Evidence multipliers. A self-declared claim still counts -- it is often all a
# new candidate has, and discarding it would empty most profiles -- but it
# counts for less than an assessment.
EVIDENCE_WEIGHT: dict[str, float] = {
    "certified": 1.0,
    "assessed": 0.95,
    "inferred": 0.7,
    "self_declared": 0.6,
}
DEFAULT_EVIDENCE = 0.6

# A missing mandatory standard caps the total here. Not zero: the candidate may
# be one short of an otherwise strong match, and telling them that is the whole
# point. Not a small penalty either, or "mandatory" would mean nothing.
MANDATORY_GAP_CAP = 0.45

# Weights across the components that do enter the score. Coverage dominates
# deliberately -- it is the only component derived from what the job actually
# published about itself.
COVERAGE_WEIGHT = 0.75
LEVEL_WEIGHT = 0.15
EVIDENCE_WEIGHT_SHARE = 0.10


@dataclass(frozen=True)
class RequiredSkill:
    """One standard a job requires, as the scorer sees it."""

    skill_id: uuid.UUID
    concept_id: uuid.UUID | None
    nos_code: str | None
    name_en: str
    nsqf_level: Decimal | None
    importance: int
    is_mandatory: bool


@dataclass(frozen=True)
class HeldSkill:
    """One standard a candidate holds."""

    skill_id: uuid.UUID
    concept_id: uuid.UUID | None
    name_en: str
    proficiency: int
    source: str


@dataclass(frozen=True)
class MatchedSkill:
    nos_code: str | None
    name_en: str
    importance: int
    is_mandatory: bool
    evidence: str
    proficiency: int


@dataclass(frozen=True)
class MissingSkill:
    skill_id: uuid.UUID
    concept_id: uuid.UUID | None
    nos_code: str | None
    name_en: str
    importance: int
    is_mandatory: bool
    nsqf_level: Decimal | None


@dataclass(frozen=True)
class MatchResult:
    """A score and, more importantly, why.

    `score` is 0-100 and exists for ordering. Everything else exists so a person
    can act on it, and so the number can be defended.
    """

    score: int
    coverage: float
    matched: list[MatchedSkill] = field(default_factory=list)
    missing: list[MissingSkill] = field(default_factory=list)
    missing_mandatory: int = 0
    level_shortfall: Decimal | None = None
    capped_by_mandatory: bool = False

    @property
    def is_eligible_shape(self) -> bool:
        """No mandatory standard missing. Eligibility to *enrol* is separate."""
        return self.missing_mandatory == 0


def _key(skill_id: uuid.UUID, concept_id: uuid.UUID | None) -> uuid.UUID:
    """Compare on concept where there is one, else on the row itself.

    A skill with no concept is a curated or unimported row; falling back to its
    own id keeps it comparable with itself rather than matching everything.
    """
    return concept_id or skill_id


def score_match(
    required: list[RequiredSkill],
    held: list[HeldSkill],
    *,
    job_level_min: Decimal | None = None,
    candidate_level: Decimal | None = None,
) -> MatchResult:
    """Score one candidate against one job. Pure: no I/O, no clock, no model."""
    if not required:
        # A job that lists no requirements cannot be matched against. Returning
        # zero is honest; returning 100 would rank empty jobs top.
        return MatchResult(score=0, coverage=0.0)

    held_by_key = {_key(h.skill_id, h.concept_id): h for h in held}

    matched: list[MatchedSkill] = []
    missing: list[MissingSkill] = []
    earned = 0.0
    total_weight = 0.0
    evidence_sum = 0.0

    for req in required:
        weight = float(max(req.importance, 1))
        total_weight += weight
        hit = held_by_key.get(_key(req.skill_id, req.concept_id))
        if hit is None:
            missing.append(
                MissingSkill(
                    skill_id=req.skill_id,
                    concept_id=req.concept_id,
                    nos_code=req.nos_code,
                    name_en=req.name_en,
                    importance=req.importance,
                    is_mandatory=req.is_mandatory,
                    nsqf_level=req.nsqf_level,
                )
            )
            continue
        evidence = EVIDENCE_WEIGHT.get(hit.source, DEFAULT_EVIDENCE)
        earned += weight
        evidence_sum += evidence
        matched.append(
            MatchedSkill(
                nos_code=req.nos_code,
                name_en=req.name_en,
                importance=req.importance,
                is_mandatory=req.is_mandatory,
                evidence=hit.source,
                proficiency=hit.proficiency,
            )
        )

    coverage = earned / total_weight if total_weight else 0.0

    if not matched:
        # Nothing in common. Returning the level and evidence components alone
        # would give every job in the catalogue a small non-zero score for
        # everyone, which is noise that ranking then has to see past.
        missing.sort(key=lambda m: (not m.is_mandatory, -m.importance, m.name_en))
        return MatchResult(
            score=0,
            coverage=0.0,
            missing=missing,
            missing_mandatory=sum(1 for m in missing if m.is_mandatory),
        )

    evidence_score = evidence_sum / len(matched)

    # Level fit: full marks when the candidate meets or exceeds the floor, and
    # tapering below it rather than falling off a cliff -- being half a level
    # short is not the same as being unqualified.
    level_score = 1.0
    shortfall: Decimal | None = None
    if job_level_min is not None:
        if candidate_level is None:
            # Unknown, not zero: most profiles have no assessed level, and
            # scoring them as level 0 would bury every new candidate.
            level_score = 0.6
        elif candidate_level >= job_level_min:
            level_score = 1.0
        else:
            shortfall = job_level_min - candidate_level
            level_score = max(0.0, 1.0 - float(shortfall) / 4.0)

    raw = (
        COVERAGE_WEIGHT * coverage
        + LEVEL_WEIGHT * level_score
        + EVIDENCE_WEIGHT_SHARE * evidence_score
    )

    missing_mandatory = sum(1 for m in missing if m.is_mandatory)
    capped = False
    if missing_mandatory:
        capped = raw > MANDATORY_GAP_CAP
        raw = min(raw, MANDATORY_GAP_CAP)

    # Most important first, so the reason reads in the order a person cares
    # about: what is mandatory and missing, then what matters most.
    missing.sort(key=lambda m: (not m.is_mandatory, -m.importance, m.name_en))
    matched.sort(key=lambda m: (not m.is_mandatory, -m.importance, m.name_en))

    return MatchResult(
        score=round(raw * 100),
        coverage=coverage,
        matched=matched,
        missing=missing,
        missing_mandatory=missing_mandatory,
        level_shortfall=shortfall,
        capped_by_mandatory=capped,
    )
