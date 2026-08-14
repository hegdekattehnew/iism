import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    role: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_email_verified: bool
    memberships: list[MembershipOut]


class EmailVerificationConfirm(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
