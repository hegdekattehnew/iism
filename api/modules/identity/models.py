import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ColumnElement,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base, one_of

# Organisations that own inventory. Sprint 3 needs the record; Sprint 4 layers
# User and Membership on top of it (ADR-010).
TENANT_TYPES = ("employer", "course_provider", "personal")

# Membership roles within a tenant. RBAC now, designed so ABAC can be layered
# on later without restructuring (ADR-012, ADR-022).
MEMBERSHIP_ROLES = ("owner", "admin", "member")

# What an invitation may offer. **`owner` is deliberately absent**: ownership is
# transferred between people who are already here, which is a different act with
# a different guard. An invitation that could mint an owner would also be a way
# to hand the organisation to a stranger who never accepted anything else.
INVITABLE_ROLES = ("admin", "member")

# How long an unaccepted invitation stays good for. Short enough that a
# forwarded mail from a departed colleague is not a standing key.
INVITE_TTL_DAYS = 7


class Tenant(Base):
    """An organisation. Not an auth concept — jobs and courses belong to one.

    Introduced in Sprint 3 ahead of authentication so that inventory has a real
    foreign key from the start. A throwaway `organisation_name` string would
    have forced an FK migration once Sprint 4 lands.
    """

    __tablename__ = "tenants"
    __table_args__ = (
        # Generated from TENANT_TYPES, not spelled again. `personal` was once
        # added to the database by hand while this copy lagged, and Alembic does
        # not diff CHECK bodies, so nothing flagged the drift.
        CheckConstraint(one_of("tenant_type", TENANT_TYPES), name="ck_tenants_type"),
        # A badge carries its evidence or it does not exist. Hand-written in
        # 0028 as well as here: Alembic does not diff CHECK bodies.
        CheckConstraint(
            "verified_at IS NULL OR ("
            "verified_by IS NOT NULL AND length(btrim(verification_note)) >= 10)",
            name="ck_tenants_verified_has_evidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column()
    tenant_type: Mapped[str] = mapped_column()
    city: Mapped[str | None] = mapped_column(default=None)

    # What a candidate sees when deciding whether to apply. Until now a job
    # listing showed a bare name with nothing behind it.
    description: Mapped[str | None] = mapped_column(Text, default=None)
    website: Mapped[str | None] = mapped_column(Text, default=None)
    logo_url: Mapped[str | None] = mapped_column(Text, default=None)
    # Deliberately NOT on the public `TenantOut`: an organisation's own inbox is
    # not something a job listing should broadcast to scrapers.
    contact_email: Mapped[str | None] = mapped_column(Text, default=None)

    # Set by an operator, never by the organisation (ADR-042). A self-asserted
    # badge is worse than none, because a candidate reads it as ours.
    #
    # **`is_verified` is derived, not stored.** It was a bare boolean from
    # Sprint 12 to Sprint 28 with no writer anywhere, so dropping it lost
    # nothing -- and a badge whose provenance can be NULL is exactly what the
    # operator surface exists to prevent. `ck_tenants_verified_has_evidence`
    # makes the unevidenced badge unrepresentable rather than merely wrong.
    # timestamptz, not naive: written from application code as UTC, and
    # `updated_at` below is naive only because 0016 made it so.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    # The operator's evidence, and the reason a candidate can be told the badge
    # means something. Cleared on revoke -- the *reason* for a revocation lives
    # in `tenant_verification_events`, which is why both exist.
    verification_note: Mapped[str | None] = mapped_column(Text, default=None)

    @hybrid_property
    def is_verified(self) -> bool:
        return self.verified_at is not None

    @is_verified.inplace.expression
    @classmethod
    def _is_verified_expression(cls) -> ColumnElement[bool]:
        return cls.verified_at.isnot(None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class User(Base):
    """A person. Identified by UUID, never by phone or email (ADR-011).

    Both identifiers are nullable and independently unique, because the two
    cohorts arrive through different doors: candidates sign in with a phone and
    may have no email at all, organisational users the reverse (ADR-032). A
    row with neither is meaningless, which the check constraint enforces.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("phone IS NOT NULL OR email IS NOT NULL", name="ck_users_has_identifier"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    phone: Mapped[str | None] = mapped_column(unique=True, index=True, default=None)
    email: Mapped[str | None] = mapped_column(unique=True, index=True, default=None)
    full_name: Mapped[str | None] = mapped_column(default=None)

    # Verified independently: holding one does not vouch for the other.
    # timestamptz, not naive: these are written from application code as UTC and
    # a naive column silently rejects an aware value.
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    # Which privacy notice and terms this person agreed to, and when (DPDP Act
    # 2023). Consent has to be provable, and consent to a text nobody can
    # identify later proves nothing. Null for accounts created before Sprint 20:
    # they never agreed through a recorded notice, and a backfilled version
    # would fabricate a record of something that did not happen.
    consent_version: Mapped[str | None] = mapped_column(default=None)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    is_active: Mapped[bool] = mapped_column(default=True)

    # Operator authority (ADR-042). Global, not scoped to any organisation, and
    # **written by no HTTP route in this product** -- only by
    # `scripts/grant_staff.py`, which needs database credentials. A back office
    # whose first feature is its own escalation path is the thing that rule
    # exists to prevent. A test scans the OpenAPI schema for any request body
    # carrying this name.
    is_staff: Mapped[bool] = mapped_column(default=False, server_default="false")
    preferred_locale: Mapped[str] = mapped_column(default="en")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", lazy="selectin", cascade="all, delete-orphan"
    )


class Membership(Base):
    """A user's role within a tenant.

    Present from day one per ADR-010 even though Sprint 4 only creates personal
    tenants — retrofitting multi-tenancy onto live user data is exactly the
    migration this avoids.
    """

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
        CheckConstraint(one_of("role", MEMBERSHIP_ROLES), name="ck_membership_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(default="member")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="memberships")
    tenant: Mapped["Tenant"] = relationship(lazy="selectin")


class Invitation(Base):
    """An offer of membership, to an address that may not have an account yet.

    **A row here is not a `Membership`.** Writing the membership at invitation
    time and marking it pending would have been fewer moving parts and one
    serious defect: an unaccepted invitation would count everywhere members are
    counted -- including the sole-owner guard in `privacy/`, which would then
    pass while the organisation still has exactly one actual human. An
    invitation is a claim about the future; a membership is a fact.

    **State is derived, never stored.** `pending`, `accepted`, `revoked` and
    `expired` are a function of three timestamps, so there is no status column
    to drift from them the first time a write path forgets one. The same
    reasoning `CourseInterest.contact_is_visible` uses.

    **This row holds an email address, and it has to.** Every other table here
    names a person by id and resolves their address at send time (see
    `notifications/models.py`); an invitee may have no account at all, so there
    is no id to name. The outbox still never stores the address: a notification
    for an invitation points at *this row*, and resolves through it -- which is
    also what makes a revoked invitation stop sending.
    """

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(one_of("role", INVITABLE_ROLES), name="ck_invitation_role"),
        # The token is the capability, so it is looked up on every acceptance.
        Index("ix_invitations_token_hash", "token_hash", unique=True),
        Index("ix_invitations_tenant_id", "tenant_id"),
        # Accepting reaches this table by address, from the sign-in path.
        Index("ix_invitations_email", "email"),
        # One *live* invitation per address per organisation, enforced in the
        # database rather than by a read-then-write the second request loses.
        # Partial, so a revoked or accepted invitation does not block a new one
        # -- created with op.execute() in 0026 and therefore listed in
        # `MANUALLY_MANAGED_INDEXES`, or the next autogenerate drops it.
        Index(
            "uq_invitations_live",
            "tenant_id",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
    )
    # Lowercased by the service before it ever reaches here, as every other
    # email lookup in this module is -- `Admin@clinic.in` and `admin@clinic.in`
    # are one mailbox, and two rows for them is two invitations to one person.
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(default="member")

    # Hashed exactly as an OTP is (`hash_secret`, HMAC-SHA256 with the app
    # secret). It is a short-lived bearer secret, not a password: `hash_secret`
    # has no work factor and must never be repurposed as though it did.
    token_hash: Mapped[str] = mapped_column(Text)

    # Who to blame, and who to name in the email. Nullable because the inviter
    # may later delete their account, and an invitation outliving them is
    # better than one that vanishes mid-flight.
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship(lazy="selectin")

    def state(self, now: datetime) -> str:
        """Derived, in one place, in the order that matters.

        Revocation beats expiry and acceptance beats both: an invitation
        revoked after it was accepted did not un-happen, and the membership it
        created is what `revoke` deliberately leaves alone.
        """
        if self.accepted_at is not None:
            return "accepted"
        if self.revoked_at is not None:
            return "revoked"
        if self.expires_at <= now:
            return "expired"
        return "pending"

    def is_open(self, now: datetime) -> bool:
        return self.state(now) == "pending"
