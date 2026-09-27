"""The assessment-provider port (ADR-017, Sprint 35 / Epic B3).

A vendor's webhook payload shape must never reach business logic directly --
the same rule ADR-017 states for a payment gateway applies just as much to an
assessment provider's callback. `parse_result` is the one seam: everything
downstream of it -- resolving the candidate, resolving the standard, writing
the `CandidateSkill` -- is vendor-agnostic and lives in `api/modules/assessment/`.
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AssessmentResult:
    """A normalised assessment outcome, independent of which vendor reported it.

    `phone` is the platform's own identity key (ADR-011) -- what an enrolling
    agency or an assessment centre already has for a candidate, not a new
    identifier invented for this integration. `standard_code` is a NOS/QP
    code (`Skill.nos_code`), which is unique in the corpus and the only
    identifier an external system could plausibly cite a standard by; this
    platform's own slugs are not something a vendor would ever hold.

    Deliberately coarse: pass/fail against a named standard, nothing else.
    Not a score, a transcript or free-text feedback -- see the module
    docstring in `api/modules/assessment/__init__.py` for why that line is
    where it is drawn.
    """

    phone: str
    standard_code: str
    passed: bool


@runtime_checkable
class AssessmentProvider(Protocol):
    """Parses one vendor's webhook payload into an `AssessmentResult`."""

    def parse_result(self, payload: dict[str, Any]) -> AssessmentResult: ...


class AssessmentError(RuntimeError):
    """The payload could not be parsed, or did not match this vendor's shape."""
