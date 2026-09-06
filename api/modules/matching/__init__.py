"""Public interface of the matching module (ADR-007, ADR-036).

Deterministic scoring only. No model client lives here and none may be added:
a score must be explainable to an employer and reproducible against a golden
set, and neither survives a generated number.
"""

from api.modules.matching.routes import router
from api.modules.matching.scoring import MatchResult, score_match
from api.modules.matching.service import courses_closing_gap, match_jobs

__all__ = ["MatchResult", "courses_closing_gap", "match_jobs", "router", "score_match"]
