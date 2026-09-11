from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import (
    TokenPair,
    get_current_user,
    get_optional_user,
    revoke_all_for_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from api.modules.identity import schemas, service
from api.modules.identity.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# Linking a second credential and creating an organisation both act on the
# signed-in account, so they sit under /me rather than /auth -- the same
# convention the candidate profile already uses.
account_router = APIRouter(prefix="/me", tags=["auth"])


def _tokens(pair: TokenPair) -> schemas.TokenPairOut:
    return schemas.TokenPairOut(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


def _signed_in(
    pair: TokenPair, *, created: bool, organisation_slug: str | None = None
) -> schemas.SignInOut:
    return schemas.SignInOut(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
        created=created,
        organisation_slug=organisation_slug,
    )


@router.post("/otp/request", response_model=schemas.OtpRequestResponse)
async def request_otp(payload: schemas.OtpRequest) -> schemas.OtpRequestResponse:
    """Send a sign-in code.

    Always reports success for a well-formed number, whether or not an account
    exists — otherwise the endpoint enumerates registered phone numbers.
    """
    ttl, debug_code = await service.request_otp(payload.phone)
    return schemas.OtpRequestResponse(sent=True, expires_in_seconds=ttl, debug_code=debug_code)


@router.post("/otp/verify", response_model=schemas.SignInOut)
async def verify_otp(
    payload: schemas.OtpVerify, db: AsyncSession = Depends(get_db_session)
) -> schemas.SignInOut:
    _, tokens, created = await service.verify_otp_and_sign_in(
        db, payload.phone, payload.code, payload.consent_version
    )
    return _signed_in(tokens, created=created)


# ------------------------------------------------------------- organisations


@router.post("/email/otp/request", response_model=schemas.OtpRequestResponse)
async def request_email_otp(payload: schemas.EmailOtpRequest) -> schemas.OtpRequestResponse:
    """Send a sign-in code to an email address.

    Same enumeration rule as the phone path: a well-formed address always gets
    the same answer, whether or not it has an account.
    """
    ttl, debug_code = await service.request_email_otp(payload.email)
    return schemas.OtpRequestResponse(sent=True, expires_in_seconds=ttl, debug_code=debug_code)


@router.post("/email/otp/verify", response_model=schemas.SignInOut)
async def verify_email_otp(
    payload: schemas.EmailOtpVerify, db: AsyncSession = Depends(get_db_session)
) -> schemas.SignInOut:
    _, tokens, created, organisation_slug = await service.verify_email_and_sign_in(
        db, payload.email, payload.code
    )
    return _signed_in(tokens, created=created, organisation_slug=organisation_slug)


@router.post("/org/register", response_model=schemas.OrgRegisterResponse)
async def register_organisation(
    payload: schemas.OrgRegisterRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User | None = Depends(get_optional_user),
) -> schemas.OrgRegisterResponse:
    """Create an organisation and its first account, for someone with neither.

    Signed out: the response is identical whether or not the address already
    has an account; only the email differs. Verifying the code that follows is
    what signs the user in, via the ordinary email path.

    **Signed in: no new account, ever.** This route used to ignore who was
    calling and mint a fresh `User` for any unfamiliar address, so a candidate
    who opened `/signup/employer` and typed a work email forked into two
    identities -- the outcome ADR-038 exists to prevent. Sprint 13 documented it
    in `CreateOrgForm.tsx`, removed the button, and left the route open; the
    homepage role chooser then put the button back. Now the organisation is
    added to the caller's own account, exactly as `POST /me/organisations`
    would. The typed address is not linked: linking a credential needs its own
    verification, and doing it silently here would be the takeover-by-typo
    `confirm_link` is built to refuse.
    """
    if user is not None:
        tenant = await service.provision_organisation(
            db, user, payload.organisation_name, payload.tenant_type
        )
        await db.commit()
        return schemas.OrgRegisterResponse(
            sent=False, expires_in_seconds=0, organisation_slug=tenant.slug
        )
    ttl, debug_code = await service.register_organisation(
        db,
        payload.email,
        payload.organisation_name,
        payload.tenant_type,
        payload.consent_version,
    )
    return schemas.OrgRegisterResponse(sent=True, expires_in_seconds=ttl, debug_code=debug_code)


@router.post("/refresh", response_model=schemas.TokenPairOut)
async def refresh(payload: schemas.RefreshRequest) -> schemas.TokenPairOut:
    tokens = await rotate_refresh_token(payload.refresh_token)
    return _tokens(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: schemas.RefreshRequest) -> None:
    await revoke_refresh_token(payload.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: User = Depends(get_current_user)) -> None:
    await revoke_all_for_user(user.id)


@router.get("/me", response_model=schemas.UserOut)
async def me(user: User = Depends(get_current_user)) -> schemas.UserOut:
    return schemas.UserOut.model_validate(user)


# ------------------------------------------ one identity, a second credential


@account_router.post("/credentials/email", response_model=schemas.OtpRequestResponse)
async def link_email_request(
    payload: schemas.LinkEmailRequest, user: User = Depends(get_current_user)
) -> schemas.OtpRequestResponse:
    """Start adding an email to the signed-in account. Writes nothing yet."""
    ttl, debug_code = await service.request_link_code("email", payload.email)
    return schemas.OtpRequestResponse(sent=True, expires_in_seconds=ttl, debug_code=debug_code)


@account_router.post("/credentials/email/verify", response_model=schemas.UserOut)
async def link_email_verify(
    payload: schemas.LinkEmailVerify,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.UserOut:
    updated = await service.confirm_link(db, user, "email", payload.email, payload.code)
    return schemas.UserOut.model_validate(updated)


@account_router.post("/credentials/phone", response_model=schemas.OtpRequestResponse)
async def link_phone_request(
    payload: schemas.LinkPhoneRequest, user: User = Depends(get_current_user)
) -> schemas.OtpRequestResponse:
    ttl, debug_code = await service.request_link_code("sms", payload.phone)
    return schemas.OtpRequestResponse(sent=True, expires_in_seconds=ttl, debug_code=debug_code)


@account_router.post("/credentials/phone/verify", response_model=schemas.UserOut)
async def link_phone_verify(
    payload: schemas.LinkPhoneVerify,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.UserOut:
    updated = await service.confirm_link(db, user, "sms", payload.phone, payload.code)
    return schemas.UserOut.model_validate(updated)


@account_router.post("/organisations", response_model=schemas.TenantOut, status_code=201)
async def create_organisation(
    payload: schemas.OrgCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.TenantOut:
    """Add an organisation to the signed-in identity.

    This is the multi-role path: a candidate asked to start hiring gets a
    second membership, not a second account (ADR-038).
    """
    tenant = await service.provision_organisation(
        db, user, payload.organisation_name, payload.tenant_type
    )
    await db.commit()
    await db.refresh(tenant)
    return schemas.TenantOut.model_validate(tenant)
