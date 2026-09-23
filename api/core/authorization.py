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
    # Deleting the organisation itself. Owner only, and separate from
    # ORG_UPDATE for the reason JOB_DELETE is separate from JOB_UPDATE: an
    # update reverses and this does not.
    ORG_DELETE = "org:delete"
    JOB_CREATE = "job:create"
    JOB_UPDATE = "job:update"
    JOB_PUBLISH = "job:publish"
    JOB_DELETE = "job:delete"
    COURSE_CREATE = "course:create"
    COURSE_UPDATE = "course:update"
    COURSE_PUBLISH = "course:publish"
    COURSE_DELETE = "course:delete"
    CANDIDATE_SHORTLIST = "candidate:shortlist"
    # A provider seeing who wants their course. The mirror of
    # CANDIDATE_SHORTLIST, and separate from it because the two disclose
    # different things to different kinds of organisation.
    LEARNER_CONTACT = "learner:contact"
    # Sprint 25, the team. Declared **without** a `publishes` argument at every
    # call site: who works here is orthogonal to what the organisation may
    # publish, so unlike LEARNER_CONTACT these ask no tenant-type question.
    MEMBER_READ = "member:read"
    MEMBER_INVITE = "member:invite"
    MEMBER_MANAGE = "member:manage"

    # ---- operator (ADR-042). Granted by `users.is_staff`, by nothing else.
    # **Never reachable from a membership role**: `ROLE_PERMISSIONS` is the only
    # thing a role can widen, and an organisation's owner must not be able to
    # verify their own organisation. A test asserts the two sets are disjoint.
    OPS_ORG_READ = "ops:org:read"
    OPS_ORG_VERIFY = "ops:org:verify"


# Seeing who else works here is the one thing every member may do. It names
# colleagues, not candidates: no contact detail, no listing, nothing about
# anybody outside the organisation.
_MEMBER: frozenset[Permission] = frozenset({Permission.ORG_READ, Permission.MEMBER_READ})
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
    Permission.LEARNER_CONTACT,
    # An admin may bring someone in, and `invite()` decides at what role: a
    # `member` only. That ceiling is enforced in the service, once, rather
    # than by a fourth permission -- it is a rule about the *argument*, and a
    # permission set cannot express one.
    Permission.MEMBER_INVITE,
}
# Deletion is the owner's alone, and so is editing the organisation itself. An
# admin can unpublish, which reverses; neither of these does.
_OWNER: frozenset[Permission] = _ADMIN | {
    Permission.JOB_DELETE,
    Permission.COURSE_DELETE,
    Permission.ORG_UPDATE,
    Permission.ORG_DELETE,
    # Changing somebody's role or removing them outright is the owner's, for
    # the reason the two above are: neither reverses by itself.
    Permission.MEMBER_MANAGE,
}

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "member": _MEMBER,
    "admin": _ADMIN,
    "owner": _OWNER,
}

# What `users.is_staff` grants, and the only route to an `OPS_` permission
# (ADR-042). A frozenset rather than a function today; when operator authority
# stops being a boolean -- somebody who may verify but not suspend -- this
# becomes a function of the user and **no route changes**, which is the whole
# reason callers ask for a Permission rather than for the flag (ADR-022).
OPERATOR_PERMISSIONS: frozenset[Permission] = frozenset(
    {Permission.OPS_ORG_READ, Permission.OPS_ORG_VERIFY}
)


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
                    # Names the tenant type rather than the verb: this same
                    # gate gates reads too, and "can publish a course" is
                    # the wrong sentence for a provider reading their own
                    # interested learners.
                    f"This is for a {expected.replace('_', ' ')} organisation",
                )
        return context

    return dependency


@dataclass(frozen=True)
class OperatorContext:
    """Who is acting, and what they may do. **There is no tenant.**

    Frozen for the reason `TenantContext` is, and separate from it for a
    different one: `require()`'s contract is that every org-scoped query filters
    on `context.tenant.id`. A nullable tenant there would make that invariant
    conditional at every existing call site, and a `None` would be aimed at
    exactly the queries that must never be unfiltered.
    """

    user: "User"
    permissions: frozenset[Permission]

    def allows(self, permission: Permission) -> bool:
        return permission in self.permissions


def require_operator(
    permission: Permission,
) -> Callable[..., Coroutine[Any, Any, OperatorContext]]:
    """A dependency granting one operator permission. No path parameter (ADR-042).

    Operator authority belongs to nobody's organisation, so there is no slug to
    resolve and no membership to read -- only `users.is_staff`, which **no HTTP
    route anywhere in this product writes**. It is set by
    `scripts/grant_staff.py`, which needs database credentials: a capability
    strictly greater than anything the API grants.

    **404, not 403**, and with FastAPI's own wording. ADR-039's enumeration
    argument does not carry here -- there is one back office and its path is not
    guessable -- but its other half does: a 403 acknowledges standing the caller
    has already proved, and a non-operator has proved none. A 403 would tell
    somebody poking at `/ops` that they had found the back office and that one
    flag on their row was all that stood in the way. A *different* detail string
    would be just as good an oracle, so the body matches an unrouted path
    exactly and a test compares the two.
    """
    if permission not in OPERATOR_PERMISSIONS:
        # At import time, not per request. A route asking for JOB_PUBLISH here
        # would otherwise 404 for ever and read as a missing route rather than
        # as a mistake; the app refusing to boot is the honest answer.
        raise ValueError(f"{permission.value} is not an operator permission")

    async def dependency(user: "User" = Depends(get_current_user)) -> OperatorContext:
        if not user.is_staff:
            # Anonymous never reaches here: `get_current_user` has already
            # answered 401, which is the opposite question and must stay
            # distinguishable from this one.
            log.warning("authz.operator_denied", permission=permission.value)
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
        if permission not in OPERATOR_PERMISSIONS:  # pragma: no cover - seam for tiers
            log.warning("authz.operator_permission_denied", permission=permission.value)
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
        # Opaque and non-personal, like `tenant_id` above. `user_id` is already
        # bound by `get_current_user`, so the access line says who acted.
        structlog.contextvars.bind_contextvars(operator=True)
        return OperatorContext(user=user, permissions=OPERATOR_PERMISSIONS)

    return dependency
