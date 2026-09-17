"""An application, and a saved job: the two rows that let the loop close.

Twenty sprints computed matches and produced no outcome -- a candidate saw
ranked vacancies with no button, and an employer saw a ranked pool it could not
reach, because ADR-037 keeps identity out of every pool payload. An application
is the candidate's own act, and the only thing that moves a name across that
line.

**Keyed on the profile, not the user.** Matching scores profiles, the employer's
ranking joins on profile ids, and erasure deletes the profile -- so an account
that exercises its right to be forgotten takes its applications with it, by the
same cascade, without privacy code having to remember this table exists.
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

# SQLAlchemy resolves ForeignKey("jobs.id") against the metadata at mapper
# configuration time, so the target module must be imported for the side
# effect -- a script importing only this module dies with NoReferencedTableError.
from api.modules.marketplace import models as _marketplace  # noqa: F401

# A closed set, like `EVENT_NAMES` and `Permission`. `applied` and `withdrawn`
# are the candidate's; the rest are the employer's.
APPLICATION_STATUSES = ("applied", "withdrawn", "shortlisted", "rejected", "hired")

# The statuses in which an employer may still see who applied. `withdrawn` is
# deliberately absent: withdrawing takes the contact details back.
LIVE_STATUSES = ("applied", "shortlisted", "hired")

# What an employer may move an application to. Neither `applied` (the
# candidate's opening move) nor `withdrawn` (theirs to take back) is here.
EMPLOYER_STATUSES = ("shortlisted", "rejected", "hired")


class Application(Base):
    """One candidate, one vacancy, once."""

    __tablename__ = "applications"
    __table_args__ = (
        # Applying twice to the same vacancy is not two applications.
        UniqueConstraint("job_id", "profile_id", name="uq_application_job_profile"),
        CheckConstraint(one_of("status", APPLICATION_STATUSES), name="ck_application_status"),
        Index("ix_applications_job_id", "job_id"),
        Index("ix_applications_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(default="applied")
    # The candidate's covering note. Bounded on the way in by the schema; Text
    # here, because a prose column with a varchar bound is a future failure.
    message: Mapped[str | None] = mapped_column(Text, default=None)

    # The consent record for the disclosure (DPDP Act 2023): when this
    # candidate's contact details became visible to this employer, and when
    # they stopped being. Withdrawal sets the second; both are kept, because
    # "was it ever shared, and for how long" is a question worth answering.
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

    job: Mapped["_marketplace.Job"] = relationship(lazy="selectin")

    @property
    def contact_is_visible(self) -> bool:
        """Whether the employer may still see who this is."""
        return self.status in LIVE_STATUSES


class SavedJob(Base):
    """A candidate's private bookmark. Shares nothing with anyone."""

    __tablename__ = "saved_jobs"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_id", name="uq_saved_job"),
        Index("ix_saved_jobs_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped["_marketplace.Job"] = relationship(lazy="selectin")
