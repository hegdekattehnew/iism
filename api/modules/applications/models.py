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
#
# `completed`/`no_show` (Sprint 37, Epic B8) are a gig engagement's outcome --
# reachable only from `hired`, and only when the underlying `Job.employment_type`
# is `"gig"` (enforced in `employer_service.set_status`, not by this CHECK,
# the same way "no required standard" is a service-layer refusal rather than a
# schema one). A permanent vacancy's `hired` stays terminal, exactly as before.
APPLICATION_STATUSES = (
    "applied",
    "withdrawn",
    "shortlisted",
    "rejected",
    "hired",
    "completed",
    "no_show",
)

# The statuses in which an employer may still see who applied. `withdrawn` is
# deliberately absent: withdrawing takes the contact details back. `completed`/
# `no_show` are both live -- the engagement is over, not the disclosure.
LIVE_STATUSES = ("applied", "shortlisted", "hired", "completed", "no_show")

# What a candidate may still take back. A subset of `LIVE_STATUSES`: once an employer
# has hired, rejected or closed out an engagement, withdrawing would rewrite their
# record rather than end the candidate's own interest.
WITHDRAWABLE_STATUSES = ("applied", "shortlisted")

# Two different questions, and a gig is where they part. A finished gig worker
# moves `hired` -> `completed`, so anything counting `status == "hired"` alone
# stops counting them. `no_show` was hired, but left the seat empty.
#   - Does this person occupy one of the vacancy's positions? (`_close_if_filled`)
FILLED_STATUSES = ("hired", "completed")
#   - Was this person ever hired? (the programme report's outcome figure)
WAS_HIRED_STATUSES = ("hired", "completed", "no_show")

# What an employer may move an application to. Neither `applied` (the
# candidate's opening move) nor `withdrawn` (theirs to take back) is here.
EMPLOYER_STATUSES = ("shortlisted", "rejected", "hired", "completed", "no_show")

# Who an `ApplicationReview` row is *about* -- not who wrote it. Two rows per
# application, one per direction, never one row with two nullable rating
# columns: that shape would let one party's review exist before the other's,
# or force one to wait on the other. `UNIQUE (application_id, subject_role)`
# on the model below is what makes each direction write-once.
REVIEW_SUBJECT_ROLES = ("poster", "worker")


class Application(Base):
    """One candidate, one vacancy, once."""

    __tablename__ = "applications"
    __table_args__ = (
        # Applying twice to the same vacancy is not two applications.
        UniqueConstraint("job_id", "profile_id", name="uq_application_job_profile"),
        CheckConstraint(one_of("status", APPLICATION_STATUSES), name="ck_application_status"),
        Index("ix_applications_job_id", "job_id"),
        Index("ix_applications_profile_id", "profile_id"),
        # The employer overview counts live and untriaged applications per vacancy with one
        # `GROUP BY job_id, status` (`matching.employer._application_counts`); this lets it read
        # the index alone.
        Index("ix_applications_job_status", "job_id", "status"),
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


class ApplicationReview(Base):
    """One direction of a gig engagement's rating (Sprint 37, Epic B8).

    Two rows per completed engagement, not one row with a rating in each
    direction: a poster rating a worker and a worker rating a poster are
    different acts by different people, and a shared row would let one
    party's review exist before the other's had anything to update. Only
    ever written once `Application.status == "completed"` -- see
    `review_service.py`. `no_show` is deliberately not reviewable: it is
    evidence about the cancellation, which the status value already carries,
    not evidence about the work.
    """

    __tablename__ = "application_reviews"
    __table_args__ = (
        UniqueConstraint("application_id", "subject_role", name="uq_application_review_direction"),
        CheckConstraint(
            one_of("subject_role", REVIEW_SUBJECT_ROLES), name="ck_review_subject_role"
        ),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_review_rating"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE")
    )
    subject_role: Mapped[str] = mapped_column()
    rating: Mapped[int] = mapped_column()
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    # Who actually submitted it, for audit -- `CandidateCertification.verified_by`'s
    # exact precedent. `SET NULL` on the author's own erasure: the review
    # about the *other* party is what this table exists to keep, and their
    # erasure must not take somebody else's earned rating with it.
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
