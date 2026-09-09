import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base, one_of

# Organisations that own inventory. Sprint 3 needs the record; Sprint 4 layers
# User and Membership on top of it (ADR-010).
TENANT_TYPES = ("employer", "course_provider", "personal")

# Membership roles within a tenant. RBAC now, designed so ABAC can be layered
# on later without restructuring (ADR-012, ADR-022).
MEMBERSHIP_ROLES = ("owner", "admin", "member")


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

    # Set by an operator, never by the organisation. A self-asserted badge is
    # worse than none, because a candidate reads it as ours. No endpoint writes
    # it yet; the column exists so the seam is there before anyone needs it.
    is_verified: Mapped[bool] = mapped_column(default=False, server_default="false")

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

    is_active: Mapped[bool] = mapped_column(default=True)
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
