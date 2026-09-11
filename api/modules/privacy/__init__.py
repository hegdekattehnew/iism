"""The data-subject rights of India's DPDP Act 2023: export and erasure.

Its own module because both operations span every other one -- identity,
the candidate profile, organisations and their listings, analytics. Letting
any one of those reach into the others would break the boundaries ADR-014
relies on; this module depends on them, and nothing depends on it.
"""

from api.modules.privacy.routes import router

__all__ = ["router"]
