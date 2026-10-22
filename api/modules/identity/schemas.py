import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from api.core.config import get_settings

TenantType = Literal["employer", "course_provider", "personal"]
MembershipRole = Literal["owner", "admin", "member"]

# What an invitation may offer -- `owner` deliberately absent, because
# ownership is transferred rather than invited. Closed on the way out so the
# generated TypeScript client types a role as a union rather than `string`;
# `tests/test_enumerations.py` holds both of these to their CHECKs.
InvitableRole = Literal["admin", "member"]

# Derived from three timestamps by `Invitation.state`, never stored, so there
# is no column for this union to disagree with -- and therefore deliberately
# **not** in `test_enumerations.py`'s table.
InvitationState = Literal["pending", "accepted", "revoked", "expired"]

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
    # How long until another code may be asked for: what the forms count down from. 0 when no
    # code was sent. The server enforces it regardless (a 429 with `Retry-After`).
    resend_after_seconds: int = 0
    # Development only; absent in any other environment (see Settings.expose_otp).
    debug_code: str | None = None


class OtpVerify(BaseModel):
    phone: PhoneStr
    code: str = Field(min_length=4, max_length=8)
    # Required only when this verification *creates* an account -- the phone
    # path provisions on first successful sign-in. Signing in to an existing
    # account needs no fresh consent.
    consent_version: str | None = Field(default=None, max_length=32)

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
    # Required only when this verification *creates* an account, which on the
    # email path happens in exactly one case: an invited address that had none
    # (Sprint 25). Signing in to an account that already exists needs no fresh
    # consent, and an unknown address with no invitation still gets 401.
    consent_version: str | None = Field(default=None, max_length=32)

    @field_validator("email", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_email(v)


def _check_capabilities(tenant_type: str, sells: bool, delivers: bool) -> None:
    """A training organisation sells, delivers, or both; an employer has neither (ADR-102).

    A value error is a 422 with the field named by the framework. The default
    (`sells_courses` true, `delivers_training` false) is an employer's too, so an employer's
    request that says nothing is valid, and one that asks for delivery is not.
    """
    if tenant_type == "employer":
        if delivers:
            raise ValueError("An employer does not deliver training")
        return
    if not (sells or delivers):
        raise ValueError("A training organisation sells courses, delivers training, or both")


class OrgRegisterRequest(BaseModel):
    """Cold registration: an address and the organisation it belongs to."""

    email: EmailStr
    organisation_name: Annotated[str, Field(min_length=2, max_length=120)]
    tenant_type: OrgTenantType = "employer"
    # What a training organisation does (Sprint 94, ADR-102). Optional and additive: absent means
    # what every provider did before they existed (sells courses, delivers nothing).
    sells_courses: bool = True
    delivers_training: bool = False
    # Required, and checked before any lookup: the answer for a missing or stale
    # version must not depend on whether the address already has an account.
    consent_version: Annotated[str, Field(min_length=1, max_length=32)]

    @field_validator("email", mode="after")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_email(v)

    @model_validator(mode="after")
    def _capabilities(self) -> "OrgRegisterRequest":
        _check_capabilities(self.tenant_type, self.sells_courses, self.delivers_training)
        return self


class OrgCreateRequest(BaseModel):
    """Creating an organisation from an account that already exists.

    No credential here: the caller is already signed in, and this is the path
    that lets one identity hold a candidate profile and an employer role
    without forking into two accounts (ADR-038).
    """

    organisation_name: Annotated[str, Field(min_length=2, max_length=120)]
    tenant_type: OrgTenantType = "employer"
    sells_courses: bool = True
    delivers_training: bool = False

    @model_validator(mode="after")
    def _capabilities(self) -> "OrgCreateRequest":
        _check_capabilities(self.tenant_type, self.sells_courses, self.delivers_training)
        return self


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


class CredentialChangedOut(TokenPairOut):
    """A sign-in credential was replaced or removed.

    Every session ended, this caller's included, so the answer carries a fresh pair: the person who
    changed their number must not be signed out by doing so.
    """

    user: "UserOut"


class SignInOut(TokenPairOut):
    """What a successful code verification returns.

    `created` and `organisation_slug` are safe to disclose **here and nowhere
    earlier**: the caller has just proved they control the phone or mailbox, so
    telling them whether the account was new reveals nothing they could not
    already learn by reading their own messages. At *request* time the same fact
    would be an enumeration oracle, which is why `OtpRequestResponse` carries
    nothing of the kind.
    """

    # True on the first successful sign-in for this identity. A returning user
    # is told they already had an account and landed on their workspace rather
    # than in the onboarding wizard.
    created: bool = False
    # The organisation this sign-in was *for*, when there is one: the one just
    # added on verification, or the only one a brand-new account holds. Lets the
    # client land exactly there rather than guessing from an unordered list.
    organisation_slug: str | None = None


class OrgRegisterResponse(OtpRequestResponse):
    """Cold registration's answer.

    Signed out: identical in shape and content for a known and an unknown
    address, `organisation_slug` always null. Signed in: no code is sent, the
    organisation is added to the caller's own account, and its slug comes back
    -- the caller is disclosing nothing about anyone but themselves.
    """

    organisation_slug: str | None = None


class TenantOut(BaseModel):
    """An organisation as the **public** sees it.

    Embedded in `JobOut` and `CourseOut`, so every field here appears on
    `/jobs` and `/courses`. `contact_email` is therefore deliberately absent —
    an organisation's inbox is not something a listing should broadcast to
    whatever scrapes it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    tenant_type: TenantType
    city: str | None = None
    description: str | None = None
    website: str | None = None
    logo_url: str | None = None
    # Set by an operator, never by the organisation itself.
    is_verified: bool = False
    # What a training organisation does (Sprint 94, ADR-102). Public: a learner reads "sells
    # courses" and "delivers training" off the page, and the header's navigation follows them.
    publishes_courses: bool = False
    delivers_training: bool = False


class OrganisationOut(TenantOut):
    """What the organisation's own members see. Adds what the public may not."""

    contact_email: str | None = None
    # What it says about itself (Sprint 94). Public on the organisation's own page, but not on
    # `TenantOut`, which is embedded in every vacancy and course.
    year_established: int | None = None
    affiliations: str | None = None
    teaching_languages: str | None = None


class OrganisationIn(BaseModel):
    """What a member may change. Everything absent from here is not theirs to set.

    Note what is missing: `slug` (a published URL), `tenant_type` (changing it
    would strand the listings already published under it) and `is_verified`
    (ours to assert, not theirs).
    """

    name: Annotated[str, Field(min_length=2, max_length=120)]
    city: Annotated[str | None, Field(max_length=120)] = None
    description: str | None = None
    website: Annotated[str | None, Field(max_length=500)] = None
    logo_url: Annotated[str | None, Field(max_length=500)] = None
    contact_email: EmailStr | None = None
    # Claims an organisation makes about itself (Sprint 94, ADR-102): shown as its own and never
    # sorted or filtered on (ADR-085). An absent field leaves the stored value alone (the
    # partial-update rule); a blank one clears it.
    year_established: Annotated[int | None, Field(ge=1800, le=2100)] = None
    affiliations: Annotated[str | None, Field(max_length=500)] = None
    teaching_languages: Annotated[str | None, Field(max_length=200)] = None

    @field_validator("year_established", mode="after")
    @classmethod
    def _not_in_the_future(cls, v: int | None) -> int | None:
        if v is not None and v > datetime.now(UTC).year:
            raise ValueError("An organisation cannot have been established in the future")
        return v

    @field_validator("contact_email", mode="after")
    @classmethod
    def _normalise(cls, v: str | None) -> str | None:
        # Lowercased like every other address in this file. It was the one that
        # was not -- `update_organisation` is the single write path in the
        # product with no service layer behind it, so a `setattr` loop over
        # `model_dump()` stored whatever was typed. This is also the address
        # `notifications/service.py` sends an organisation's mail to.
        return normalise_email(v) if v is not None else None


class CapabilitiesIn(BaseModel):
    """What a training organisation does now (Sprint 94, ADR-102). An absent field is left alone."""

    sells_courses: bool | None = None
    delivers_training: bool | None = None


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
    consent_version: str | None = None
    consented_at: datetime | None = None
    preferred_locale: str
    # Operator authority (ADR-042). Read-only and read-only for ever: no
    # request shape in this product carries this name, and a test scans the
    # OpenAPI schema to keep it that way. It is here so the interface can offer
    # the back office to somebody who holds it, and a fact about them that they
    # are entitled to see in their own export.
    is_staff: bool = False
    # Same rule as `is_staff`, one tier down (ADR-044, Sprint 37, BL-7.3):
    # read-only for ever, no request shape may carry this name.
    staff_tier: str | None = None
    # The raw stamp, so a client can say when; the two derived facts below are what screens
    # branch on.
    consent_withdrawn_at: datetime | None = None
    memberships: list[MembershipOut] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def consent_current(self) -> bool:
        """Is the notice this person agreed to the one in force? Never blocks anything: a stale
        version shows a prompt to read and confirm (Sprint 72)."""
        return self.consent_version == get_settings().privacy_notice_version

    @computed_field  # type: ignore[prop-decorator]
    @property
    def consent_withdrawn(self) -> bool:
        return self.consent_withdrawn_at is not None


# ------------------------------------------------------------ the team (S25)


class InviteIn(BaseModel):
    """Offer somebody membership.

    `EmailStr`, and lowercased, for the reason every other address here is:
    `Admin@clinic.in` and `admin@clinic.in` are one mailbox, and two
    invitations to one person is a confusing thing to receive.
    """

    email: EmailStr
    role: InvitableRole = "member"

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return normalise_email(v)


class InvitationOut(BaseModel):
    """An invitation, as the organisation that sent it sees it.

    Carries the address, because the people reading this screen are the ones
    who typed it and need to see whether they typed it right. It does **not**
    carry the token: that reached one mailbox, and a member list is not a place
    to hand it to everybody else with `MEMBER_INVITE`.
    """

    id: uuid.UUID
    email: str
    role: InvitableRole
    state: InvitationState
    expires_at: datetime
    created_at: datetime
    invited_by: str | None = None


class InvitationPreview(BaseModel):
    """What the holder of a token is told **before** they accept.

    The organisation and the role, and nothing else. The token is a capability
    to *join*, not a capability to read: who else is a member, who sent it and
    what the organisation has published all stay behind the acceptance.
    """

    organisation: str
    organisation_slug: str
    tenant_type: OrgTenantType
    role: InvitableRole


class InvitationClaimed(BaseModel):
    """A code has been sent to the address the invitation was written to.

    The address is **masked**. The person holding the token got it from that
    mailbox and already knows it; a forwarded link should not hand it to
    somebody else in full, and the hint is enough to recognise your own.
    """

    sent: bool
    expires_in_seconds: int
    email_hint: str
    # Development only, exactly as `OtpRequestResponse.debug_code` is.
    debug_code: str | None = None


class InvitationVerify(BaseModel):
    """The code, and consent. **No address** -- it comes off the invitation."""

    code: Annotated[str, Field(min_length=4, max_length=8)]
    consent_version: str | None = Field(default=None, max_length=32)


class InvitationAccepted(BaseModel):
    organisation_slug: str
    role: MembershipRole


class MemberOut(BaseModel):
    """A colleague.

    The address is here and the phone is not: an organisation's members need to
    reach each other by mail, and a personal mobile number is a different
    disclosure that nobody made by accepting an invitation.
    """

    user_id: uuid.UUID
    role: MembershipRole
    full_name: str | None = None
    email: str | None = None
    since: datetime
    # Whether this row is the caller's own, so the interface can say "you" and
    # refuse to offer somebody a button that removes themselves by surprise.
    is_you: bool = False


class MemberRoleIn(BaseModel):
    role: MembershipRole


class OwnershipTransferIn(BaseModel):
    """Hand the organisation to somebody already in it.

    `then` is what happens to the person handing over: stay as an `admin`
    (the default -- it keeps them able to help and can be reversed by the new
    owner) or `leave`. There is no "stay as owner": that is a role change, and
    this act means exactly one thing.
    """

    user_id: uuid.UUID
    then: Literal["admin", "leave"] = "admin"
