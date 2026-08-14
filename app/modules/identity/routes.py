from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import get_current_user
from app.modules.identity import service
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    EmailVerificationConfirm,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest, db: AsyncSession = Depends(get_db_session)
) -> TokenPair:
    _, tokens = await service.register_user(db, data)
    return tokens


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db_session)) -> TokenPair:
    _, tokens = await service.authenticate_user(db, data)
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db_session)) -> TokenPair:
    return await service.refresh_tokens(db, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: LogoutRequest) -> None:
    await service.logout(data.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: User = Depends(get_current_user)) -> None:
    await service.logout_all(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/verify-email/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_email_verification(user: User = Depends(get_current_user)) -> None:
    await service.request_email_verification(user)


@router.post("/verify-email/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_email_verification(
    data: EmailVerificationConfirm, db: AsyncSession = Depends(get_db_session)
) -> None:
    await service.confirm_email_verification(db, data.token)


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_password_reset(
    data: PasswordResetRequest, db: AsyncSession = Depends(get_db_session)
) -> None:
    await service.request_password_reset(db, data.email)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    data: PasswordResetConfirm, db: AsyncSession = Depends(get_db_session)
) -> None:
    await service.confirm_password_reset(db, data.token, data.new_password)


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    url = await service.get_google_authorization_url()
    return RedirectResponse(url)


@router.get("/google/callback", response_model=TokenPair)
async def google_callback(
    code: str, state: str, db: AsyncSession = Depends(get_db_session)
) -> TokenPair:
    _, tokens = await service.handle_google_callback(db, code, state)
    return tokens
