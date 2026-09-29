"""Public interface of the matching module (ADR-007, ADR-036).

Deterministic scoring only. No model client lives here and none may be added:
a score must be explainable to an employer and reproducible against a golden
set, and neither survives a generated number.

The employer console is the same `score_match` with its arguments the other way
round, which is why it lives here rather than in a module of its own.
"""

from api.modules.matching.employer import candidates_for_job, market_scarce_skills, score_profiles
from api.modules.matching.employer_routes import (
    candidate_card,
    mount_employer_console,
)
from api.modules.matching.employer_routes import org_router as employer_org_router
from api.modules.matching.provider_routes import market_router as provider_market_router
from api.modules.matching.provider_routes import org_router as provider_org_router
from api.modules.matching.routes import router
from api.modules.matching.schemas import CandidateCardOut
from api.modules.matching.scoring import (
    DEFAULT_WEIGHTS,
    SERIOUS_MATCH_SCORE,
    MatchResult,
    ScoreWeights,
    score_match,
)
from api.modules.matching.service import (
    RoleAlignment,
    course_role_alignment,
    courses_closing_gap,
    match_jobs,
)

__all__ = [
    "CandidateCardOut",
    "candidates_for_job",
    "market_scarce_skills",
    "candidate_card",
    "score_profiles",
    "MatchResult",
    "RoleAlignment",
    "SERIOUS_MATCH_SCORE",
    "DEFAULT_WEIGHTS",
    "ScoreWeights",
    "course_role_alignment",
    "employer_org_router",
    "provider_market_router",
    "provider_org_router",
    "courses_closing_gap",
    "match_jobs",
    "mount_employer_console",
    "router",
    "score_match",
]
