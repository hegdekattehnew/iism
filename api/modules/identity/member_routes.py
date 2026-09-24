"""Who works here: the member list, invitations, and the two ways out.

**Two routers, and the split is the point.** Everything an organisation does to
its own team hangs off `/org/{org_slug}`, where `require()` already resolves
membership and answers a non-member with 404 rather than 403 (ADR-038).
Accepting cannot live there: the person accepting is **not yet a member**, so
that same dependency would 404 them out of their own invitation. The acceptance
routes are keyed on the token instead, which is the capability that reached
their mailbox.

**No `publishes` argument anywhere in this file.** Who works at an organisation
is orthogonal to what it may publish, so unlike `LEARNER_CONTACT` these gates
ask no tenant-type question -- an employer and a training provider manage a team
identically.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.authorization import Permission, TenantContext, require
from api.core.database import get_db_session
from api.core.security import get_current_user
from api.modules.identity import invitations as service
from api.modules.identity import schemas
from api.modules.identity import service as sign_in_service
from api.modules.identity.models import Invitation, User

router = APIRouter(prefix="/org/{org_slug}", tags=["team"])

# `/invitations/{token}` deliberately carries no org slug: the token names the
# organisation, and requiring the caller to know its slug as well would mean
# the invitation email had to disclose one more thing than it needs to.
public_router = APIRouter(prefix="/invitations", tags=["team"])

CanReadMembers = Depends(require(Permission.MEMBER_READ))
CanInvite = Depends(require(Permission.MEMBER_INVITE))
CanManage = Depends(require(Permission.MEMBER_MANAGE))


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


# ------------------------------------------------------------------- members


@router.get("/members", response_model=list[schemas.MemberOut])
async def list_members(
    context: TenantContext = CanReadMembers,
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.MemberOut]:
    """Everybody in this organisation. Any member may see this.

    It names colleagues, not candidates: nothing here crosses the line
    ADR-037 draws around the people outside the organisation.
    """
    return [
        schemas.MemberOut(
            user_id=user.id,
            role=membership.role,
            full_name=user.full_name,
            email=user.email,
            since=membership.created_at,
            is_you=user.id == context.user.id,
        )
        for membership, user in await service.list_members(db, context.tenant.id)
    ]


@router.patch("/members/{user_id}", response_model=schemas.MemberOut)
async def set_member_role(
    user_id: uuid.UUID,
    payload: schemas.MemberRoleIn,
    context: TenantContext = CanManage,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.MemberOut:
    """Owner only. Refuses to demote the organisation's last owner (409)."""
    membership, user = await service.set_role(
        db,
        tenant_id=context.tenant.id,
        actor_user_id=context.user.id,
        user_id=user_id,
        role=payload.role,
    )
    return schemas.MemberOut(
        user_id=user.id,
        role=membership.role,
        full_name=user.full_name,
        email=user.email,
        since=membership.created_at,
        is_you=user.id == context.user.id,
    )


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID,
    context: TenantContext = CanManage,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Owner only. The last owner cannot be removed (409)."""
    await service.remove_member(
        db, tenant_id=context.tenant.id, actor_user_id=context.user.id, user_id=user_id
    )


@router.post("/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_organisation(
    context: TenantContext = CanReadMembers,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Show yourself out.

    Gated on `MEMBER_READ` -- the weakest thing every member holds -- because
    leaving is not a management act. It runs through the **same** last-owner
    guard as removal: the question "would this leave nobody in charge?" does
    not change depending on who is asking it.
    """
    await service.leave(db, tenant_id=context.tenant.id, user=context.user)


# --------------------------------------------------------------- invitations


@router.get("/invitations", response_model=list[schemas.InvitationOut])
async def list_invitations(
    context: TenantContext = CanInvite,
    db: AsyncSession = Depends(get_db_session),
) -> list[schemas.InvitationOut]:
    """Every invitation this organisation has sent, spent ones included.

    Spent ones are kept on screen because "did we ever invite her, and what
    happened?" is the question this list exists to answer, and a filter that
    hides the answer makes it useless on the one day somebody needs it.
    """
    now = datetime.now(UTC)
    return [
        _invitation_out(invitation, now, inviter)
        for invitation, inviter in await service.list_invitations(db, context.tenant.id)
    ]


@router.post(
    "/invitations", response_model=schemas.InvitationOut, status_code=status.HTTP_201_CREATED
)
async def create_invitation(
    payload: schemas.InviteIn,
    context: TenantContext = CanInvite,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.InvitationOut:
    """Invite somebody by email.

    **The response is identical whether or not that address already has an
    account** -- Sprint 12's lesson, which was learned by shipping the
    opposite. The difference between the two cases reaches the mailbox, not the
    caller: an existing account is asked to sign in and accept, a stranger is
    walked through creating one.

    An admin may invite a `member` only; asking for more is a 403.
    """
    invitation, _token = await service.invite(
        db,
        tenant=context.tenant,
        actor=context.user,
        actor_role=context.role,
        email=payload.email,
        role=payload.role,
    )
    return _invitation_out(
        invitation, datetime.now(UTC), context.user.full_name or context.user.email
    )


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    context: TenantContext = CanInvite,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Withdraw an offer. An already-accepted one is a 409: that membership is
    a separate fact with its own guard, and undoing it here would be a way past
    the last-owner check."""
    await service.revoke(db, tenant_id=context.tenant.id, invitation_id=invitation_id)


# ------------------------------------------------------------ accepting (public)


@public_router.get("/{token}", response_model=schemas.InvitationPreview)
async def preview_invitation(
    token: str, db: AsyncSession = Depends(get_db_session)
) -> schemas.InvitationPreview:
    """What am I being asked to join?

    Unauthenticated: the holder of the token has not signed in yet, and may
    have no account at all. It returns the organisation and the role and
    **nothing else** -- not who invited them, not who else is a member, not
    what the organisation has published.
    """
    invitation = await service.invitation_for_token(db, token)
    tenant = invitation.tenant
    return schemas.InvitationPreview(
        organisation=tenant.name,
        organisation_slug=tenant.slug,
        tenant_type=tenant.tenant_type,
        role=invitation.role,
    )


@public_router.post("/{token}/claim", response_model=schemas.InvitationClaimed)
async def claim_invitation(
    token: str, db: AsyncSession = Depends(get_db_session)
) -> schemas.InvitationClaimed:
    """I hold this invitation and have no account. Send me a code.

    This is the path for an address with no account at all, and it is the
    **only** thing that permits `verify_email_and_sign_in` to create one --
    which is the riskiest seam in the product, so it is worth being explicit
    about what makes it safe:

    * the address is taken from the invitation, never from the request, so a
      forwarded link cannot mint an account at an address of the holder's
      choosing;
    * the invitation was written by somebody who holds `MEMBER_INVITE` at a
      real organisation, so the account is not the caller's own idea;
    * they still have to read the code out of that mailbox.

    An address that already has an account may use this too -- it simply signs
    them in and accepts. One flow, both cases, which also means the response
    does not say which this was.
    """
    invitation, ttl, debug_code = await service.claim(db, token)
    return schemas.InvitationClaimed(
        sent=True,
        expires_in_seconds=ttl,
        email_hint=service.mask_address(invitation.email),
        debug_code=debug_code,
    )


@public_router.post("/{token}/verify", response_model=schemas.SignInOut)
async def verify_invitation_code(
    token: str,
    payload: schemas.InvitationVerify,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.SignInOut:
    """Finish the stranger's path: code in, signed-in account out.

    **The address is never in the request.** It is read off the invitation,
    which is why this route exists at all rather than the client calling
    `/auth/email/otp/verify` directly -- the preview deliberately does not
    disclose the address, and a form that asked for one would let a forwarded
    link mint an account at an address of the holder's choosing.

    It delegates to `verify_email_and_sign_in` rather than reimplementing it:
    the `PENDING_INVITE_KEY` that `claim` wrote is what permits that function
    to create an account, and the acceptance happens inside it. One creation
    path, one acceptance path, both already tested.
    """
    invitation = await service.invitation_for_token(db, token)
    _, tokens, created, organisation_slug = await sign_in_service.verify_email_and_sign_in(
        db, invitation.email, payload.code, payload.consent_version
    )
    return schemas.SignInOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        created=created,
        organisation_slug=organisation_slug,
    )


@public_router.post("/{token}/accept", response_model=schemas.InvitationAccepted)
async def accept_invitation(
    token: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.InvitationAccepted:
    """Join, as the signed-in identity. One more membership, never a second
    account (ADR-038).

    The **other** acceptance path -- an address with no account at all -- runs
    through `verify_email_and_sign_in`, because creating the account is what
    that endpoint does and forking a second one here is what ADR-038 forbids.
    """
    invitation = await service.invitation_for_token(db, token)
    # `accept()` records the event itself, because the *other* acceptance path
    # runs inside `verify_email_and_sign_in` and would otherwise go unmeasured.
    membership = await service.accept(db, invitation=invitation, user=user)
    tenant = invitation.tenant
    return schemas.InvitationAccepted(
        organisation_slug=tenant.slug,
        role=membership.role,
    )
