"""How a candidate is scored against a job (ADR-007, ADR-036).

Deterministic and auditable. **No model is called here and none may be added** —
an employer or a regulator can be told exactly why a score is what it is, and a
golden set can only measure something reproducible.

The output is a *reason structure*, not a number with a sentence attached. The
interface renders that structure, so the explanation cannot drift away from the
score it explains.

Six components, and each uses a signal that already exists rather than one
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
* **Experience** — the candidate's years against the job's minimum (Sprint 23).
  ADR-007 always named experience; until now nothing read it.
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
EVIDENCE_WEIGHT_SHARE = 0.10

# Experience was carved out of level's 0.15, not added on top. For a candidate
# who meets both floors, 0.08 x 1 + 0.07 x 1 is the 0.15 x 1 it replaced, so the
# change is score-neutral for everyone who fits and moves only those who fall
# short. That identity is what kept all five golden pairs where they were; a
# test holds it, and it is the thing to preserve when tuning either weight.
LEVEL_WEIGHT = 0.08
EXPERIENCE_WEIGHT = 0.07

# Years short of the job's minimum at which the experience component reaches
# zero. A tapering judgement, not a sourced number: being a year short of three
# is not the same as having none.
EXPERIENCE_TAPER_YEARS = 3.0

# What counts as a serious candidate, not merely a technical match: no
# mandatory standard missing scores well above this, and a near-miss still
# clears it. Lives here, not in a caller, so the alert sweep and the
# operator-facing programme report agree on one number rather than two
# modules independently deciding 60 is enough.
SERIOUS_MATCH_SCORE = 60


@dataclass(frozen=True)
class ScoreWeights:
    """The business's dials on the scorer, gathered into one value (Sprint 33,
    BL-2.1) so re-tuning them is a configuration change, not a deployment.

    A *value passed in*, never read here: `score_match` stays pure (ADR-036)
    precisely because nothing inside this module calls `get_settings()`.
    `matching.service.weights_from_settings()` is where configuration and the
    scorer actually meet, and it lives there rather than here for that reason.

    Defaults are every number this scorer has used since Sprint 10 -- calling
    `score_match` with no `weights` argument at all reproduces every score
    from before this change, exactly, which is what keeps `make evaluate`
    bit-identical.
    """

    coverage: float = COVERAGE_WEIGHT
    level: float = LEVEL_WEIGHT
    experience: float = EXPERIENCE_WEIGHT
    evidence_share: float = EVIDENCE_WEIGHT_SHARE
    mandatory_gap_cap: float = MANDATORY_GAP_CAP
    experience_taper_years: float = EXPERIENCE_TAPER_YEARS


DEFAULT_WEIGHTS = ScoreWeights()


@dataclass(frozen=True)
class RequiredSkill:
    """One standard a job requires, as the scorer sees it."""

    skill_id: uuid.UUID
    concept_id: uuid.UUID | None
    nos_code: str | None
    name: str
    nsqf_level: Decimal | None
    importance: int
    is_mandatory: bool


@dataclass(frozen=True)
class HeldSkill:
    """One standard a candidate holds."""

    skill_id: uuid.UUID
    concept_id: uuid.UUID | None
    name: str
    proficiency: int
    source: str


@dataclass(frozen=True)
class MatchedSkill:
    nos_code: str | None
    name: str
    importance: int
    is_mandatory: bool
    evidence: str
    proficiency: int


@dataclass(frozen=True)
class MissingSkill:
    skill_id: uuid.UUID
    concept_id: uuid.UUID | None
    nos_code: str | None
    name: str
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
    experience_shortfall: int | None = None
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
    job_min_years: int | None = None,
    candidate_years: int | None = None,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> MatchResult:
    """Score one candidate against one job. Pure: no I/O, no clock, no model.

    `weights` defaults to every number this scorer has always used; a caller
    passes its own only to re-tune deliberately (BL-2.1)."""
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
                    name=req.name,
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
                name=req.name,
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
        missing.sort(key=lambda m: (not m.is_mandatory, -m.importance, m.name))
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

    # Experience fit: the same shape as level. Never a penalty for exceeding
    # the job's *maximum* -- declining the over-qualified is a hiring decision
    # this product does not get to make (ADR-037).
    #
    # Known limitation, stated rather than hidden: `years_experience` is
    # NOT NULL DEFAULT 0, so "never filled in" reads as "no experience". It is
    # not derived from `CandidateExperience` here -- that would be I/O, and this
    # function stays pure (ADR-036). None means the caller did not say, and is
    # treated as a fit rather than a zero.
    experience_score = 1.0
    years_short: int | None = None
    if job_min_years and candidate_years is not None and candidate_years < job_min_years:
        years_short = job_min_years - candidate_years
        experience_score = max(0.0, 1.0 - years_short / weights.experience_taper_years)

    raw = (
        weights.coverage * coverage
        + weights.level * level_score
        + weights.experience * experience_score
        + weights.evidence_share * evidence_score
    )

    missing_mandatory = sum(1 for m in missing if m.is_mandatory)
    capped = False
    if missing_mandatory:
        capped = raw > weights.mandatory_gap_cap
        raw = min(raw, weights.mandatory_gap_cap)

    # Most important first, so the reason reads in the order a person cares
    # about: what is mandatory and missing, then what matters most.
    missing.sort(key=lambda m: (not m.is_mandatory, -m.importance, m.name))
    matched.sort(key=lambda m: (not m.is_mandatory, -m.importance, m.name))

    return MatchResult(
        score=round(raw * 100),
        coverage=coverage,
        matched=matched,
        missing=missing,
        missing_mandatory=missing_mandatory,
        level_shortfall=shortfall,
        experience_shortfall=years_short,
        capped_by_mandatory=capped,
    )
