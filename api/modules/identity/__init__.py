"""Public interface of the identity module (ADR-009, ADR-010, ADR-032)."""

from api.modules.identity.models import (
    MEMBERSHIP_ROLES,
    TENANT_TYPES,
    Membership,
    Tenant,
    User,
)
from api.modules.identity.routes import router
from api.modules.identity.schemas import TenantOut, TenantType, UserOut, normalise_phone
from api.modules.identity.service import request_otp, verify_otp_and_sign_in

__all__ = [
    "MEMBERSHIP_ROLES",
    "TENANT_TYPES",
    "Membership",
    "Tenant",
    "TenantOut",
    "TenantType",
    "User",
    "UserOut",
    "normalise_phone",
    "request_otp",
    "router",
    "verify_otp_and_sign_in",
]
