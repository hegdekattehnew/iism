"""Registering interest in a course, and the provider's view of who did.

Its own module, a **sibling** of `applications/` rather than an extension of
it -- the precedent ADR-026 set when `course_publishing.py` stayed beside
`publishing.py` instead of being generalised into it. The difference is sharper
here: a vacancy publishes required standards, so an applicant can be scored;
a course publishes what it teaches, so an interested learner cannot be, and a
shared abstraction would have to invent the second scorer ADR-037 forbids.
`applications/__init__.py` also states that nothing depends on it, and that has
to stay true.

**This module holds the product's second deliberate disclosure.** Every
provider-facing payload elsewhere is de-identified by construction. Registering
interest is the exception, because the learner chose it: it shares their name,
contact and district with that provider, for that course, and withdrawing takes
it back.
"""

from api.modules.interests.models import (
    INTEREST_STATUSES,
    LIVE_STATUSES,
    PROVIDER_STATUSES,
    CourseInterest,
)
from api.modules.interests.provider_routes import router as provider_router
from api.modules.interests.routes import router

__all__ = [
    "INTEREST_STATUSES",
    "LIVE_STATUSES",
    "PROVIDER_STATUSES",
    "CourseInterest",
    "provider_router",
    "router",
]
