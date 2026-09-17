"""Applying for a vacancy, and saving one for later.

Its own module because it sits between three others -- the vacancy
(marketplace), the candidate (marketplace's profile), and the ranking that
decides what an employer sees (matching) -- and letting any of those reach into
the others would break the boundaries ADR-014 relies on. It depends on them;
nothing depends on it.

**This module holds the product's one deliberate disclosure.** Every employer
payload elsewhere is de-identified by construction (ADR-037). An application is
the exception, because the candidate chose it: applying shares their name and
contact with that employer, for that vacancy, and withdrawing takes it back.
"""

from api.modules.applications.models import (
    APPLICATION_STATUSES,
    EMPLOYER_STATUSES,
    LIVE_STATUSES,
    Application,
    SavedJob,
)
from api.modules.applications.routes import router

__all__ = [
    "APPLICATION_STATUSES",
    "EMPLOYER_STATUSES",
    "LIVE_STATUSES",
    "Application",
    "SavedJob",
    "router",
]
