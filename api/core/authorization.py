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

import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity.models import Membership, Tenant, User


class Permission(StrEnum):
    """A closed set, for the same reason `EVENT_NAMES` is closed: an open string
    becomes forty spellings of the same idea within a month, and no audit
    survives that."""

    ORG_READ = "org:read"
    JOB_CREATE = "job:create"
    JOB_UPDATE = "job:update"
    JOB_PUBLISH = "job:publish"
    JOB_DELETE = "job:delete"
    CANDIDATE_SHORTLIST = "candidate:shortlist"


_MEMBER: frozenset[Permission] = frozenset({Permission.ORG_READ})
_ADMIN: frozenset[Permission] = _MEMBER | {
    Permission.JOB_CREATE,
    Permission.JOB_UPDATE,
    Permission.JOB_PUBLISH,
    Permission.CANDIDATE_SHORTLIST,
}
# Deletion is the owner's alone. An admin can unpublish, which reverses; nothing
# else on this surface does.
_OWNER: frozenset[Permission] = _ADMIN | {Permission.JOB_DELETE}

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

    user: User
    tenant: Tenant
    role: str
    permissions: frozenset[Permission]

    def allows(self, permission: Permission) -> bool:
        return permission in self.permissions


async def _context_for(db: AsyncSession, user: User, slug: str) -> TenantContext:
    row = (
        await db.execute(
            select(Membership, Tenant)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(Membership.user_id == user.id, Tenant.slug == slug)
        )
    ).first()
    if row is None:
        # Deliberately indistinguishable from "no such organisation".
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    membership, tenant = row
    return TenantContext(
        user=user,
        tenant=tenant,
        role=membership.role,
        permissions=ROLE_PERMISSIONS.get(membership.role, frozenset()),
    )


def require(
    permission: Permission,
) -> Callable[..., Coroutine[Any, Any, TenantContext]]:
    """A dependency granting one permission in the organisation named by the path.

    Use as `context: TenantContext = Depends(require(Permission.JOB_PUBLISH))`
    on any route carrying an `{org_slug}` path parameter.
    """

    async def dependency(
        org_slug: str = Path(...),
        db: AsyncSession = Depends(get_db_session),
        user: User = Depends(get_current_user),
    ) -> TenantContext:
        context = await _context_for(db, user, org_slug)
        if not context.allows(permission):
            # 403 here, not 404: the caller has already proved membership, so
            # the organisation's existence is not news to them. Telling them
            # their role is insufficient is the useful answer.
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Your role ({context.role}) does not permit {permission.value}",
            )
        return context

    return dependency


async def tenant_ids_for(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Every tenant this user belongs to. One identity, many roles (ADR-038)."""
    return list(
        (await db.scalars(select(Membership.tenant_id).where(Membership.user_id == user_id))).all()
    )
