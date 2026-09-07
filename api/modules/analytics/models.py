"""What people actually did (ADR-025).

v1 is free to every actor and the revenue model is deferred, which makes
measurement the substitute for a price signal. Nothing recorded anything before
this, so "the recommendations are good" could only ever be an opinion.

It ships with matching rather than after it for two reasons. A behavioural
re-ranker (ADR-036) can only be built on history that was already being
collected, and the first weeks of a scoring surface are exactly the data you
cannot go back and gather.

**Nothing here may carry personal data.** ADR-023 excludes resume text, Aadhaar
and assessment results from analytics by an explicit redaction rule, and the
`payload` column is the obvious place for such a thing to leak in. It holds ids
and counts, never free text a candidate typed.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base

# A closed set, deliberately. An open string column becomes forty spellings of
# the same event within a month, and no analysis survives that.
EVENT_NAMES = (
    "matches_viewed",
    "match_opened",
    "gap_viewed",
    "course_recommended",
    "course_opened",
    # Employer console. Nameless by construction: the surface never sees a
    # candidate's identity, so neither can the event.
    "employer_overview_viewed",
    "employer_shortlist_viewed",
)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        CheckConstraint(
            "name IN ('matches_viewed', 'match_opened', 'gap_viewed', "
            "'course_recommended', 'course_opened', 'employer_overview_viewed', "
            "'employer_shortlist_viewed')",
            name="ck_analytics_event_name",
        ),
        Index("ix_analytics_events_name_time", "name", "occurred_at"),
        Index("ix_analytics_events_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64))

    # Nullable: anonymous browsing is a real and interesting case, and requiring
    # a user would silently drop it.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    # What the event was about -- a job, a course, a skill. Deliberately not a
    # foreign key: an event about something later deleted is still a fact about
    # what happened, and a cascade would quietly rewrite history.
    subject_type: Mapped[str | None] = mapped_column(String(32), default=None)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(default=None)

    # Ids and counts only. See the module docstring.
    payload: Mapped[dict | None] = mapped_column(JSONB, default=None)

    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
