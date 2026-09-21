"""Interest in a course: the row that closes the third actor's loop.

The product's whole pitch is "here is your gap, and the courses that close it".
For twenty-three sprints it then offered the learner nothing to press, and told
the provider nothing at all -- they published into silence. This is Sprint 21's
application, for the course side.

**Interest, not enrolment.** Whether somebody actually enrolled is a fact the
provider owns, in their own system; a status this platform cannot verify would
drift from reality the first week. What this product can know is that a learner
said "I want this", and that is what the row records.

**Keyed on the profile, not the user** -- the same reason `applications/models.py`
gives: erasure deletes the profile, so an account exercising its right to be
forgotten takes its interests with it by the same cascade.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base, one_of

# SQLAlchemy resolves ForeignKey("courses.id") against the metadata at mapper
# configuration time, so the target module must be imported for the side
# effect -- a script importing only this module dies with NoReferencedTableError.
from api.modules.marketplace import models as _marketplace  # noqa: F401

# A closed set, like `APPLICATION_STATUSES`. `registered` and `withdrawn` are
# the learner's; `contacted` is the provider's.
INTEREST_STATUSES = ("registered", "withdrawn", "contacted")

# The statuses in which a provider may still see who this is. `withdrawn` is
# deliberately absent: withdrawing takes the contact details back.
LIVE_STATUSES = ("registered", "contacted")

# What a provider may set. Neither `registered` (the learner's opening move) nor
# `withdrawn` (theirs to take back) is here.
PROVIDER_STATUSES = ("contacted",)


class CourseInterest(Base):
    """One learner, one course, once."""

    __tablename__ = "course_interests"
    __table_args__ = (
        # Registering twice for the same course is not two interests.
        UniqueConstraint("course_id", "profile_id", name="uq_course_interest_course_profile"),
        CheckConstraint(one_of("status", INTEREST_STATUSES), name="ck_course_interest_status"),
        Index("ix_course_interests_course_id", "course_id"),
        Index("ix_course_interests_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(default="registered")
    # What the learner wants the provider to know -- "evenings only", "I can
    # start in March". Bounded on the way in by the schema; Text here, because
    # a prose column with a varchar bound is a future failure.
    message: Mapped[str | None] = mapped_column(Text, default=None)

    # The consent record for the disclosure (DPDP Act 2023): when this
    # learner's contact details became visible to this provider, and when they
    # stopped being. Both are kept -- "was it ever shared, and for how long" is
    # a question worth being able to answer.
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

    course: Mapped["_marketplace.Course"] = relationship(lazy="selectin")

    @property
    def contact_is_visible(self) -> bool:
        """Whether the provider may still see who this is."""
        return self.status in LIVE_STATUSES
