import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

TenantType = Literal["employer", "course_provider", "personal"]
MembershipRole = Literal["owner", "admin", "member"]

# E.164-ish. Deliberately permissive on country code but strict on shape, so
# the same person cannot end up with two accounts through formatting variance.
PhoneStr = Annotated[str, Field(min_length=8, max_length=16)]

# Organisations sign in by email (ADR-038). Lowercased on the way in for the
# same reason phones are normalised: one person, one account, however they
# happened to type it.
OrgTenantType = Literal["employer", "course_provider"]


def normalise_email(value: str) -> str:
    return value.strip().lower()


def normalise_phone(value: str) -> str:
    """One canonical form per number.

    Indian users write the same number as 9876543210, 09876543210,
    +91 98765 43210 and 919876543210. Without normalisation each of those
    becomes a separate account.
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    return "+" + digits


class OtpRequest(BaseModel):
    phone: PhoneStr

    @field_validator("phone")
    @classmethod
    def _normalise(cls, v: str) -> str:
        normalised = normalise_phone(v)
        if len(normalised) < 11:
            raise ValueError("Phone number looks too short")
        return normalised


class OtpRequestResponse(BaseModel):
    sent: bool
    expires_in_seconds: int
    # Development only; absent in any other environment (see Settings.expose_otp).
    debug_code: str | None = None


class OtpVerify(BaseModel):
    phone: PhoneStr
    code: str = Field(min_length=4, max_length=8)

    @field_validator("phone")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_phone(v)


class EmailOtpRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_email(v)


class EmailOtpVerify(BaseModel):
    email: EmailStr
    code: Annotated[str, Field(min_length=4, max_length=8)]

    @field_validator("email", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_email(v)


class OrgRegisterRequest(BaseModel):
    """Cold registration: an address and the organisation it belongs to."""

    email: EmailStr
    organisation_name: Annotated[str, Field(min_length=2, max_length=120)]
    tenant_type: OrgTenantType = "employer"

    @field_validator("email", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_email(v)


class OrgCreateRequest(BaseModel):
    """Creating an organisation from an account that already exists.

    No credential here: the caller is already signed in, and this is the path
    that lets one identity hold a candidate profile and an employer role
    without forking into two accounts (ADR-038).
    """

    organisation_name: Annotated[str, Field(min_length=2, max_length=120)]
    tenant_type: OrgTenantType = "employer"


class LinkEmailRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_email(v)


class LinkEmailVerify(EmailOtpVerify):
    pass


class LinkPhoneRequest(BaseModel):
    phone: PhoneStr

    @field_validator("phone", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_phone(v)


class LinkPhoneVerify(BaseModel):
    phone: PhoneStr
    code: Annotated[str, Field(min_length=4, max_length=8)]

    @field_validator("phone", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_phone(v)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    tenant_type: TenantType
    city: str | None = None


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: MembershipRole
    tenant: TenantOut


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str | None = None
    email: str | None = None
    full_name: str | None = None
    phone_verified_at: datetime | None = None
    # Exposed so the interface can tell a linked-and-verified identifier from
    # one merely typed in. Both look the same otherwise, and the difference is
    # what a second credential is for.
    email_verified_at: datetime | None = None
    preferred_locale: str
    memberships: list[MembershipOut] = Field(default_factory=list)
