"""Permissions, resolved from membership role (ADR-012, ADR-022, ADR-039).

For eleven sprints `get_current_user` answering *is this person signed in* was
the whole of authorization, while `Membership.role` was written once and read
nowhere. This is the layer both of those ADRs describe.

**Permission-based, role-derived.** Callers ask for a permission, never for a
role — that is ADR-022, and it is what lets ADR-012's eventual move to ABAC
change how the set is computed without touching a single route. Today the set
comes from a static map; tomorrow it might come from attributes of the resource.
The call sites do not care.

**The tenant is named by the request and granted by the membership.** It is not
carried in the token, for three reasons: switching workspaces must not require
re-issuing tokens; one person can hold two tabs open as two different
organisations, which a token-borne context makes impossible; and a claim baked
into a 15-minute access token outlives a membership revoked in the meantime.

**A tenant the caller is not a member of is a 404, never a 403.** A 403 confirms
the organisation exists, which is a disclosure in its own right — an employer
can discover a competitor's account simply by guessing slugs.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user

if TYPE_CHECKING:  # pragma: no cover - typing only
    # Imported for annotations only. At runtime the models are pulled in inside
    # `_context_for`, because `api.modules.identity` now imports this module for
    # its own organisation routes -- the same cycle `get_current_user` avoids
    # the same way.
    from api.modules.identity.models import Tenant, User


log = structlog.get_logger("iism.authz")


class Permission(StrEnum):
    """A closed set, for the same reason `EVENT_NAMES` is closed: an open string
    becomes forty spellings of the same idea within a month, and no audit
    survives that."""

    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    JOB_CREATE = "job:create"
    JOB_UPDATE = "job:update"
    JOB_PUBLISH = "job:publish"
    JOB_DELETE = "job:delete"
    COURSE_CREATE = "course:create"
    COURSE_UPDATE = "course:update"
    COURSE_PUBLISH = "course:publish"
    COURSE_DELETE = "course:delete"
    CANDIDATE_SHORTLIST = "candidate:shortlist"


_MEMBER: frozenset[Permission] = frozenset({Permission.ORG_READ})
# Roles stay type-agnostic: an admin of any organisation holds both publishing
# sets, and the `publishes` half of `require()` decides which one their tenant
# may actually use. Splitting the role map by tenant type instead would mean two
# ladders to keep in step, and a role that means different things in different
# rooms.
_ADMIN: frozenset[Permission] = _MEMBER | {
    Permission.JOB_CREATE,
    Permission.JOB_UPDATE,
    Permission.JOB_PUBLISH,
    Permission.COURSE_CREATE,
    Permission.COURSE_UPDATE,
    Permission.COURSE_PUBLISH,
    Permission.CANDIDATE_SHORTLIST,
}
# Deletion is the owner's alone, and so is editing the organisation itself. An
# admin can unpublish, which reverses; neither of these does.
_OWNER: frozenset[Permission] = _ADMIN | {
    Permission.JOB_DELETE,
    Permission.COURSE_DELETE,
    Permission.ORG_UPDATE,
}

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "member": _MEMBER,
    "admin": _ADMIN,
    "owner": _OWNER,
}


@dataclass(frozen=True)
class TenantContext:
    """Who is acting, in which organisation, with what they may do.

    Frozen: a handler that could widen its own permissions mid-request would
    make this layer decorative.
    """

    user: "User"
    tenant: "Tenant"
    role: str
    permissions: frozenset[Permission]

    def allows(self, permission: Permission) -> bool:
        return permission in self.permissions


# A personal workspace is not an organisation. Every candidate is provisioned as
# `owner` of one (ADR-010 wants everybody to have a membership from day one), so
# without this filter a candidate's own personal slug resolved as a tenant
# context and their `owner` role carried JOB_CREATE, JOB_PUBLISH and
# CANDIDATE_SHORTLIST -- letting anyone read the employer console's aggregate
# pool and publish a vacancy attributed to "Personal workspace".
ORGANISATION_TYPES = ("employer", "course_provider")

# What each kind of organisation may publish. Nothing enforced this before, so a
# course provider could post vacancies and an employer could publish training.
PUBLISHES: dict[str, str] = {"job": "employer", "course": "course_provider"}


async def _context_for(db: AsyncSession, user: "User", slug: str) -> TenantContext:
    from sqlalchemy import select

    from api.modules.identity.models import Membership, Tenant  # local: avoids a cycle

    row = (
        await db.execute(
            select(Membership, Tenant)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(
                Membership.user_id == user.id,
                Tenant.slug == slug,
                Tenant.tenant_type.in_(ORGANISATION_TYPES),
            )
        )
    ).first()
    if row is None:
        # One answer for "no such organisation", "not a member" and "that is a
        # personal workspace". Distinguishing them tells a prober which slugs
        # exist -- to the *caller*. The log may say more, and should: a
        # multi-tenant product that cannot answer "who was refused which
        # organisation" has no audit trail at all, and this was silent.
        log.warning("authz.tenant_denied", org_slug=slug, reason="no_membership")
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    membership, tenant = row
    # Same reasoning as `user_id` in `get_current_user`: resolved in a
    # dependency, bound here, and visible on the access line because the
    # middleware is pure ASGI. Opaque ids and a role name, nothing personal.
    structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id), tenant_role=membership.role)
    return TenantContext(
        user=user,
        tenant=tenant,
        role=membership.role,
        permissions=ROLE_PERMISSIONS.get(membership.role, frozenset()),
    )


def require(
    permission: Permission,
    publishes: str | None = None,
) -> Callable[..., Coroutine[Any, Any, TenantContext]]:
    """A dependency granting one permission in the organisation named by the path.

    `publishes` names the kind of listing the route writes -- `"job"` or
    `"course"` -- and asks the second question the permission set cannot:
    membership answers *may this person act here*, never *is this the right kind
    of organisation*. A course provider holds `JOB_CREATE` in their own tenant,
    so without this a provider could post vacancies.

    **The two checks are one declaration on purpose.** They were separate at
    first -- `require(...)` in the signature and a `require_publisher_of(...)`
    call in the body -- and three of the eight publishing writes were shipped
    without the second: `update_job`, `unpublish_job` and `unpublish_course`.
    A guard a handler has to remember to call is a guard that eventually is not
    called, and `CLAUDE.md` meanwhile asserted it was called everywhere. Now the
    route cannot express the permission without also answering the type
    question.

    Use as `context: TenantContext = Depends(require(Permission.JOB_PUBLISH, "job"))`
    on any route carrying an `{org_slug}` path parameter.
    """

    async def dependency(
        org_slug: str = Path(...),
        db: AsyncSession = Depends(get_db_session),
        user: "User" = Depends(get_current_user),
    ) -> TenantContext:
        context = await _context_for(db, user, org_slug)
        if not context.allows(permission):
            # 403 here, not 404: the caller has already proved membership, so
            # the organisation's existence is not news to them. Telling them
            # their role is insufficient is the useful answer.
            log.warning(
                "authz.permission_denied",
                permission=permission.value,
                role=context.role,
            )
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Your role ({context.role}) does not permit {permission.value}",
            )
        if publishes is not None:
            expected = PUBLISHES[publishes]
            if context.tenant.tenant_type != expected:
                log.warning(
                    "authz.wrong_tenant_type",
                    publishes=publishes,
                    expected=expected,
                    actual=context.tenant.tenant_type,
                )
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    f"Only a {expected.replace('_', ' ')} can publish a {publishes}",
                )
        return context

    return dependency
