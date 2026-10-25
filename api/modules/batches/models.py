"""A batch: one run of one course at one centre (Sprint 98, ADR-103, BL-18.5).

A course says what is taught; a batch says **when and where it is taught, and to how many**. It
belongs to a centre (so to the organisation that delivers) and names the course (which may be sold
by another organisation, in which case the delivery authorisation of Sprint 97 must hold when the
batch is made and published).

**What a batch is *now* is derived, never stored** (ADR-025, ADR-068). The stored `status` is only
what a person decided: `draft`, `published`, `cancelled`. Whether a published batch is open, full,
running or finished is a function of today's date, its seats and the learners enrolled
(`phases.phase`), because a stored `running` is wrong the morning after and a stored seat counter
drifts the first time somebody withdraws or erases their account. A cancelled batch keeps **why**
(`cancel_reason`, a closed set) and never free text: what leaves the building is the notice's fixed
words, and the learner reads the reason code as a sentence.

`BatchInterest` is a learner's interest in a batch, kept apart from `CourseInterest` for ADR-071's
reason (a model never holds a foreign key into a module it may not import, and a course interest
discloses to the seller while a batch interest discloses to the one who runs it: the centre and its
organisation's owners and admins, never the seller). Registered by the learner (Sprint 100), who
chooses the disclosure and takes it back by withdrawing.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of

# `course_id` and `centre_id` point at `courses` and `tenants`, `profile_id` at the candidate's
# profile; SQLAlchemy resolves a ForeignKey against the metadata, so the targets are imported for
# the side effect (cross-module foreign keys).
from api.modules.identity import models as _identity_models  # noqa: F401
from api.modules.marketplace import models as _marketplace_models  # noqa: F401

BATCH_STATUSES = ("draft", "published", "cancelled")
BATCH_MODES = ("in_person", "hybrid", "online")
# Why a batch was cancelled. A closed set, so the notice is fixed words and the reason is never
# free text that could carry somebody's number.
CANCEL_REASONS = (
    "by_organisation",  # the delivering organisation or its centre's manager cancelled it
    "arrangement_ended",  # the seller ended the authorisation it was made under
    "course_unavailable",  # the course was unpublished, taken down or deleted
    "centre_closed",  # its centre closed
)

# `attended` (Sprint 100) is the centre's own report that a learner came: only after the batch has
# started, and only from `enrolled`.
INTEREST_STATUSES = ("registered", "withdrawn", "contacted", "enrolled", "attended")
# Who may still be seen / counted; `withdrawn` takes the contact back, as for a course.
LIVE_INTEREST_STATUSES = ("registered", "contacted", "enrolled", "attended")
# What takes a seat: a learner the centre has enrolled, and one who then came. **Seats left is
# `seats` minus these**, derived and never a counter (ADR-068).
TAKEN_STATUSES = ("enrolled", "attended")
# What a centre may set. `registered` and `withdrawn` are the learner's.
CENTRE_STATUSES = ("contacted", "enrolled", "attended")


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (
        CheckConstraint(one_of("status", BATCH_STATUSES), name="ck_batches_status"),
        CheckConstraint(one_of("mode", BATCH_MODES), name="ck_batches_mode"),
        CheckConstraint(
            "cancel_reason IS NULL OR " + one_of("cancel_reason", CANCEL_REASONS),
            name="ck_batches_cancel_reason",
        ),
        # A batch that was cancelled says why and when, and only a cancelled one does.
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL)",
            name="ck_batches_cancelled_pair",
        ),
        CheckConstraint("seats >= 1 AND seats <= 5000", name="ck_batches_seats"),
        CheckConstraint("ends_on >= starts_on", name="ck_batches_dates"),
        CheckConstraint("fee_inr IS NULL OR fee_inr >= 0", name="ck_batches_fee"),
        Index("ix_batches_centre_id", "centre_id"),
        Index("ix_batches_course_id", "course_id"),
        Index("ix_batches_status_starts", "status", "starts_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    # A centre is a child tenant (ADR-102); its parent is the delivering organisation, read through
    # the centre and never stored beside it, so the two cannot disagree.
    centre_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))

    # What the organisation calls this run ("Morning batch"); optional, the course title does not
    # repeat here.
    label: Mapped[str | None] = mapped_column(default=None)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    seats: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(default="in_person")
    # Days and hours as the centre states them ("Mon-Fri, 9 to 1"). A claim, not a calendar.
    schedule: Mapped[str | None] = mapped_column(default=None)
    # **The centre's own statement**, overriding the course's fee for this run when set (ADR-103);
    # NULL means "the course's fee". Never a sort or a filter on its own.
    fee_inr: Mapped[int | None] = mapped_column(Integer, default=None)

    status: Mapped[str] = mapped_column(default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    cancel_reason: Mapped[str | None] = mapped_column(default=None)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BatchInterest(Base):
    """One learner, one batch, once."""

    __tablename__ = "batch_interests"
    __table_args__ = (
        UniqueConstraint("batch_id", "profile_id", name="uq_batch_interest_batch_profile"),
        CheckConstraint(one_of("status", INTEREST_STATUSES), name="ck_batch_interest_status"),
        Index("ix_batch_interests_batch_id", "batch_id"),
        Index("ix_batch_interests_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(default="registered")
    message: Mapped[str | None] = mapped_column(Text, default=None)
    contact_shared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    contact_revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
