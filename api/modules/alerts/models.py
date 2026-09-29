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
