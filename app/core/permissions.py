import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import get_current_user
from app.modules.identity.models import Membership, User


async def require_verified_email(user: User = Depends(get_current_user)) -> User:
    if not user.is_email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email verification required")
    return user


async def _get_membership(db: AsyncSession, user: User, tenant_id: uuid.UUID) -> Membership | None:
    return await db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.tenant_id == tenant_id)
    )


def require_tenant_role(*roles: str):
    async def dependency(
        x_tenant_id: uuid.UUID = Header(alias="X-Tenant-Id"),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> Membership:
        membership = await _get_membership(db, user, x_tenant_id)
        if membership is None or membership.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Insufficient permissions for this tenant"
            )
        return membership

    return dependency


def require_tenant_role_path(*roles: str):
    async def dependency(
        tenant_id: uuid.UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> Membership:
        membership = await _get_membership(db, user, tenant_id)
        if membership is None or membership.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Insufficient permissions for this tenant"
            )
        return membership

    return dependency


def require_platform_role(*roles: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.platform_role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient platform permissions")
        return user

    return dependency


def require_tenant_role_or_platform_staff(*tenant_roles: str):
    async def dependency(
        x_tenant_id: uuid.UUID = Header(alias="X-Tenant-Id"),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> User:
        if user.platform_role is not None:
            return user
        membership = await _get_membership(db, user, x_tenant_id)
        if membership is None or membership.role not in tenant_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Insufficient permissions for this tenant"
            )
        return user

    return dependency
