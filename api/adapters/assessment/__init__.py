"""Assessment-provider adapters (ADR-017, Sprint 35). Import a factory, not
an implementation."""

from functools import lru_cache

from api.adapters.assessment.base import AssessmentError, AssessmentProvider, AssessmentResult
from api.adapters.assessment.console import ConsoleAssessmentProvider


@lru_cache
def get_assessment_provider() -> AssessmentProvider:
    """Chosen by configuration. A real vendor (an SSC-affiliated assessment
    agency) slots in here behind the same protocol once BL-3.1's business
    dependency -- a signed partnership -- exists."""
    return ConsoleAssessmentProvider()


__all__ = [
    "AssessmentError",
    "AssessmentProvider",
    "AssessmentResult",
    "ConsoleAssessmentProvider",
    "get_assessment_provider",
]
