"""Public interface of the identity module (ADR-009, ADR-010, ADR-032)."""

from api.modules.identity.centre_staff_routes import router as centre_staff_router
from api.modules.identity.consent import (
    is_paused,
    require_not_paused,
    restore_consent,
    withdraw_consent,
)
from api.modules.identity.dependencies import get_current_candidate
from api.modules.identity.invitations import lock_ownership_of
from api.modules.identity.member_routes import public_router as invitation_router
from api.modules.identity.member_routes import router as team_router
from api.modules.identity.models import (
    CENTRE_ROLES,
    INVITABLE_ROLES,
    INVITATION_ROLES,
    MEMBERSHIP_ROLES,
    TENANT_TYPES,
    Invitation,
    Membership,
    Tenant,
    User,
)
from api.modules.identity.routes import account_router, router
from api.modules.identity.schemas import TenantOut, TenantType, UserOut, normalise_phone
from api.modules.identity.service import (
    provision_candidate,
    request_otp,
    verify_otp_and_sign_in,
)
from api.modules.identity.tenant_routes import router as organisation_router

__all__ = [
    "account_router",
    "centre_staff_router",
    "get_current_candidate",
    "CENTRE_ROLES",
    "INVITABLE_ROLES",
    "INVITATION_ROLES",
    "Invitation",
    "invitation_router",
    "is_paused",
    "lock_ownership_of",
    "MEMBERSHIP_ROLES",
    "TENANT_TYPES",
    "Membership",
    "Tenant",
    "TenantOut",
    "TenantType",
    "User",
    "UserOut",
    "normalise_phone",
    "organisation_router",
    "provision_candidate",
    "request_otp",
    "require_not_paused",
    "restore_consent",
    "router",
    "team_router",
    "verify_otp_and_sign_in",
    "withdraw_consent",
]
