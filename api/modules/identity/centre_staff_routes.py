"""Who runs a training centre: the organisation's side (Sprint 96, ADR-102).

Everything hangs off the **organisation's** slug (`/org/{org}/centres/{centre}/managers`), where
`require()` has already resolved the caller's membership and the capability, and `centre_for`
answers a centre that is not this organisation's with the 404 of one that does not exist. A centre's
manager reaches none of this: it needs `CENTRE_MANAGE`, an admin's and an owner's.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, centre_for, require
from api.core.database import get_db_session
from api.modules.identity import centre_staff as service
from api.modules.identity import schemas
from api.modules.identity.models import Invitation

router = APIRouter(prefix="/org/{org_slug}/centres/{centre_slug}/managers", tags=["centres"])

CanManageCentres = Depends(require(Permission.CENTRE_MANAGE, "centre"))


def _invitation_out(
    invitation: Invitation, now: datetime, inviter: str | None
) -> schemas.InvitationOut:
    return schemas.InvitationOut(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        state=invitation.state(now),
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        invited_by=inviter,
    )


@router.get("", response_model=schemas.CentreStaffOut)
async def list_managers(
    centre_slug: str,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.CentreStaffOut:
    """The centre's managers and every invitation it has had."""
    centre = await centre_for(db, context, centre_slug)
    now = datetime.now(UTC)
    return schemas.CentreStaffOut(
        managers=[
            schemas.MemberOut(
                user_id=user.id,
                role=membership.role,
                full_name=user.full_name,
                email=user.email,
                since=membership.created_at,
                is_you=user.id == context.user.id,
            )
            for membership, user in await service.managers_of(db, centre)
        ],
        invitations=[
            _invitation_out(invitation, now, inviter)
            for invitation, inviter in await service.invitations_of(db, centre)
        ],
    )


@router.post("", response_model=schemas.InvitationOut, status_code=status.HTTP_201_CREATED)
async def invite_manager(
    centre_slug: str,
    payload: schemas.ManagerInviteIn,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.InvitationOut:
    """Ask somebody to run this centre.

    **Identical whether or not that address already has an account**, as the organisation's own
    invitations are (Sprint 12's lesson): the difference reaches the mailbox, not the caller.
    """
    centre = await centre_for(db, context, centre_slug)
    invitation = await service.invite_manager(
        db, parent=context.tenant, centre=centre, actor=context.user, email=payload.email
    )
    return _invitation_out(
        invitation, datetime.now(UTC), context.user.full_name or context.user.email
    )


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    centre_slug: str,
    invitation_id: uuid.UUID,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Withdraw an invitation that has not been accepted (409 if it has)."""
    centre = await centre_for(db, context, centre_slug)
    await service.revoke_invitation(
        db, parent=context.tenant, centre=centre, invitation_id=invitation_id
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_manager(
    centre_slug: str,
    user_id: uuid.UUID,
    context: TenantContext = CanManageCentres,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Take a manager out of the centre. The centre and the organisation are untouched."""
    centre = await centre_for(db, context, centre_slug)
    await service.remove_manager(
        db, parent=context.tenant, centre=centre, actor=context.user, user_id=user_id
    )
