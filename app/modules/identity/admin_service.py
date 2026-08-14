from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import Tenant, User
from app.modules.identity.schemas import AdminOrganizationInviteRequest, StaffInviteRequest
from app.modules.identity.service import (
    _create_tenant_with_owner,
    _get_user_by_email,
    request_account_claim,
)


async def invite_organization(
    db: AsyncSession, data: AdminOrganizationInviteRequest
) -> tuple[User, Tenant]:
    if await _get_user_by_email(db, data.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=data.email, full_name=data.full_name, hashed_password=None)
    db.add(user)
    await db.flush()
    tenant = await _create_tenant_with_owner(db, user, data.organization_name, data.tenant_type)
    await db.commit()
    await db.refresh(user)

    await request_account_claim(user)
    return user, tenant


async def invite_staff(db: AsyncSession, data: StaffInviteRequest) -> User:
    if await _get_user_by_email(db, data.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=None,
        platform_role=data.platform_role,
        is_email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await request_account_claim(user)
    return user
