"""The back office: operator authority, and the verified badge it grants.

A leaf module (ADR-014). It depends on `identity` and `marketplace`; nothing
depends on it. Authority here is **global and granted by `users.is_staff`
alone** -- never by a membership role, so an organisation's owner cannot verify
their own organisation. See ADR-042.
"""

from api.modules.operations.models import VERIFICATION_DECISIONS, TenantVerificationEvent
from api.modules.operations.routes import router
from api.modules.operations.service import set_staff, staff_roster

__all__ = [
    "VERIFICATION_DECISIONS",
    "TenantVerificationEvent",
    "router",
    "set_staff",
    "staff_roster",
]
