"""Who has already been told about which vacancy.

One row per (job, candidate), written when an alert is queued. It exists for a
single reason: **an alert must never be sent twice**. A job board that mails
the same vacancy to the same person every time a sweep runs is a job board
people filter into a folder, and the unique constraint is what makes that
impossible rather than unlikely.

**Keyed on the profile, not the user** -- the same reason `applications` and
`interests` are: erasure deletes the profile, so the record of what somebody
was told goes with it by the same cascade.

The row carries no score and no reason. What the sweep decided is measurable
from `analytics_events`; keeping a copy here would be a second source of truth
about a number that can be recomputed.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base

# SQLAlchemy resolves ForeignKey("jobs.id") against the metadata at mapper
# configuration time, so the target module must be imported for the side
# effect -- a script importing only this module dies with NoReferencedTableError.
from api.modules.marketplace import models as _marketplace  # noqa: F401


class JobAlert(Base):
    """One person, one vacancy, told once."""

    __tablename__ = "job_alerts"
    __table_args__ = (
        UniqueConstraint("job_id", "profile_id", name="uq_job_alert_job_profile"),
        # The daily-cap query: how many alerts has this candidate had lately.
        Index("ix_job_alerts_profile_created", "profile_id", "created_at"),
        Index("ix_job_alerts_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SponsorIntent(Base):
    """An employer's offer to sponsor the one standard a candidate lacks (ADR-048).

    One row per (vacancy, candidate), so an offer can be made once and a
    candidate is never prompted twice about the same vacancy by the same act.
    The unique constraint is what makes that a property of the database rather
    than an intention -- `JobAlert`'s own reasoning, one table over.

    **The employer never learns who it was.** The route that creates a row takes
    the de-identified reference the console already shows, resolves it
    server-side inside that vacancy's own near-miss pool, and never returns the
    profile, the user or whether the candidate responded. What the candidate
    receives names the organisation, the standard and the course, and links to
    the vacancy, where applying is the act that discloses them (ADR-037).

    `notified_at` is NULL when the candidate was not told -- they switched off
    unsolicited messages, or had reached today's cap. The offer is still a fact
    about the employer's intent, and the employer is deliberately not told which
    of the two happened: an opt-out is a fact about the candidate.

    Keyed on the profile, not the user, for the reason `applications` and
    `job_alerts` are: erasure deletes the profile and this goes with it.
    """

    __tablename__ = "sponsor_intents"
    __table_args__ = (
        UniqueConstraint("job_id", "profile_id", name="uq_sponsor_intent_job_profile"),
        Index("ix_sponsor_intents_job_id", "job_id"),
        # The daily-cap query: how much unsolicited mail has this candidate had.
        Index("ix_sponsor_intents_profile_created", "profile_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), default=None
    )
    offered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
