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


def require_tenant_role(*roles: str):
    async def dependency(
        x_tenant_id: uuid.UUID = Header(alias="X-Tenant-Id"),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> Membership:
        membership = await db.scalar(
            select(Membership).where(
                Membership.user_id == user.id, Membership.tenant_id == x_tenant_id
            )
        )
        if membership is None or membership.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Insufficient permissions for this tenant"
            )
        return membership

    return dependency
