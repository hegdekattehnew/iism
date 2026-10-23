"""Who may deliver whose courses (Sprint 97, ADR-102, ADR-103, BL-18.15).

A training organisation may sell courses, deliver training, or both. When one delivers a course
that **another** sells, the seller has to say yes: that is a `CourseDeliveryAuthorisation`.
Delivering a course you sell yourself needs no row at all (own delivery is automatic).

**The state is derived from timestamps, never stored** (ADR-025's rule, `CourseInterest`'s and
`Invitation`'s way), so no column can say "approved" while the row says it ended:

    requested   not approved, not ended      -- a partner asked, the provider has not answered
    approved    approved, not ended          -- the partner may create batches of that course
    declined    ended, never approved        -- the provider said no (or the partner withdrew)
    revoked     ended after being approved   -- either side withdrew it later

A provider that **invites** a partner has decided already, so that row is created approved: its
invitation is its approval, and the partner can end it (revoke) but is not asked to accept an
obligation, because nothing is owed until the partner makes a batch.

`course_id` NULL means **every course the provider sells**. Two partial unique indexes keep one
open row per (provider, partner, scope): the unique index is the arbiter of a double tap, as it is
for a duplicate application (ADR-052).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of

# `course_id` points at `courses` and `provider_id`/`partner_id` at `tenants`; SQLAlchemy resolves a
# ForeignKey against the metadata, so the targets are imported for the side effect (cross-module
# foreign keys, with the comment saying why).
from api.modules.identity import models as _identity_models  # noqa: F401
from api.modules.marketplace import models as _marketplace_models  # noqa: F401

SIDES = ("provider", "partner")
STATES = ("requested", "approved", "declined", "revoked")


class CourseDeliveryAuthorisation(Base):
    __tablename__ = "course_delivery_authorisations"
    __table_args__ = (
        CheckConstraint(one_of("initiated_by", SIDES), name="ck_delivery_initiated_by"),
        CheckConstraint(
            "ended_by_side IS NULL OR ended_by_side IN ('provider', 'partner')",
            name="ck_delivery_ended_by_side",
        ),
        # An ending names who ended it, and a row that names who ended it has ended.
        CheckConstraint(
            "(ended_at IS NULL) = (ended_by_side IS NULL)", name="ck_delivery_ended_pair"
        ),
        # Delivering your own course needs no authorisation, so a row between an organisation and
        # itself is always a mistake.
        CheckConstraint("provider_id <> partner_id", name="ck_delivery_two_organisations"),
        # One open row per (provider, partner, scope): all of a provider's courses, or one.
        Index(
            "uq_delivery_open_all",
            "provider_id",
            "partner_id",
            unique=True,
            postgresql_where=text("course_id IS NULL AND ended_at IS NULL"),
        ),
        Index(
            "uq_delivery_open_course",
            "provider_id",
            "partner_id",
            "course_id",
            unique=True,
            postgresql_where=text("course_id IS NOT NULL AND ended_at IS NULL"),
        ),
        Index("ix_delivery_provider_id", "provider_id"),
        Index("ix_delivery_partner_id", "partner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    # NULL: every course the provider sells. Otherwise exactly that one.
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), default=None
    )
    initiated_by: Mapped[str] = mapped_column()
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ended_by_side: Mapped[str | None] = mapped_column(default=None)
    ended_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    @property
    def state(self) -> str:
        """Derived, so it can never disagree with the timestamps it is read from."""
        if self.ended_at is not None:
            return "revoked" if self.approved_at is not None else "declined"
        return "approved" if self.approved_at is not None else "requested"
