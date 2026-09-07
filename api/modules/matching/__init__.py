"""Public interface of the matching module (ADR-007, ADR-036).

Deterministic scoring only. No model client lives here and none may be added:
a score must be explainable to an employer and reproducible against a golden
set, and neither survives a generated number.

The employer console is the same `score_match` with its arguments the other way
round, which is why it lives here rather than in a module of its own.
"""

from api.modules.matching.employer_routes import (
    mount_employer_console,
)
from api.modules.matching.employer_routes import org_router as employer_org_router
from api.modules.matching.routes import router
from api.modules.matching.scoring import MatchResult, score_match
from api.modules.matching.service import courses_closing_gap, match_jobs

__all__ = [
    "MatchResult",
    "employer_org_router",
    "courses_closing_gap",
    "match_jobs",
    "mount_employer_console",
    "router",
    "score_match",
]
