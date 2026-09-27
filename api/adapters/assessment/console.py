"""Reference implementation: a plain JSON shape, no vendor signed yet.

BL-3.1's own acceptance criteria name "a signed provider partnership" as a
business dependency, not an engineering one -- this exists so the webhook
path can be exercised end to end before that partnership lands, the same
role `ConsoleNotificationProvider` plays for SMS. It refuses to run in
production for the same reason: a stand-in that quietly accepted requests in
production would look exactly like a working, verified integration while
nobody had actually checked anything.

Unlike `ConsolePaymentProvider` (Sprint 34), this has a real caller today --
`api/modules/assessment/routes.py` -- so it keeps a legitimate development
success path rather than refusing unconditionally.
"""

import logging

from api.adapters.assessment.base import AssessmentError, AssessmentResult
from api.core.config import get_settings

__all__ = ["ConsoleAssessmentProvider"]

logger = logging.getLogger("iism.assessment")


class ConsoleAssessmentProvider:
    def parse_result(self, payload: dict) -> AssessmentResult:
        if get_settings().environment == "production":
            raise AssessmentError("ConsoleAssessmentProvider must not be used in production")
        try:
            phone = str(payload["phone"])
            standard_code = str(payload["standard_code"])
            outcome = str(payload["outcome"])
        except KeyError as exc:
            raise AssessmentError(f"missing field: {exc}") from exc
        if outcome not in ("pass", "fail"):
            raise AssessmentError(f"unknown outcome: {outcome!r} (expected 'pass' or 'fail')")
        # Standard code and outcome only -- a phone number is personal data
        # (ADR-023) and does not belong in a log line.
        logger.warning("assessment result parsed (standard=%s, outcome=%s)", standard_code, outcome)
        return AssessmentResult(phone=phone, standard_code=standard_code, passed=outcome == "pass")
