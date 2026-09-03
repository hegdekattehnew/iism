from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db_session
from api.core.security import (
    get_current_user,
    revoke_all_for_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from api.modules.identity import schemas, service
from api.modules.identity.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request", response_model=schemas.OtpRequestResponse)
async def request_otp(payload: schemas.OtpRequest) -> schemas.OtpRequestResponse:
    """Send a sign-in code.

    Always reports success for a well-formed number, whether or not an account
    exists — otherwise the endpoint enumerates registered phone numbers.
    """
    ttl, debug_code = await service.request_otp(payload.phone)
    return schemas.OtpRequestResponse(sent=True, expires_in_seconds=ttl, debug_code=debug_code)


@router.post("/otp/verify", response_model=schemas.TokenPairOut)
async def verify_otp(
    payload: schemas.OtpVerify, db: AsyncSession = Depends(get_db_session)
) -> schemas.TokenPairOut:
    _, tokens, _ = await service.verify_otp_and_sign_in(db, payload.phone, payload.code)
    return schemas.TokenPairOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=schemas.TokenPairOut)
async def refresh(payload: schemas.RefreshRequest) -> schemas.TokenPairOut:
    tokens = await rotate_refresh_token(payload.refresh_token)
    return schemas.TokenPairOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: schemas.RefreshRequest) -> None:
    await revoke_refresh_token(payload.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: User = Depends(get_current_user)) -> None:
    await revoke_all_for_user(user.id)


@router.get("/me", response_model=schemas.UserOut)
async def me(user: User = Depends(get_current_user)) -> schemas.UserOut:
    return schemas.UserOut.model_validate(user)
