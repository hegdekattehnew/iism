"""A message to us, and what happened to it (Sprint 57, BL-14.3, ADR-067).

**Its own table, not `analytics_events` and not the notification outbox.** Analytics is purged on a
schedule and `record()` swallows its own failures: right for measurement, disqualifying for a
complaint. The outbox is addressed to a person and resolves the address at send time; a stranger's
message has no recipient to resolve. This is a record somebody has to answer, and the answer is
dated.

Three kinds, because they are three different promises:

* `contact`: anyone may write, to say anything.
* `grievance`: a complaint about how personal data is handled or about content on the marketplace.
  The grievance page promises an acknowledgement within a day and a resolution within fifteen.
* `data_request`: see, correct, erase or nominate. **Signed in only**, because the account is the
  proof of who is asking; a stranger asking for somebody's data is the attack the rule exists for.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of

GRIEVANCE_KINDS = ("contact", "grievance", "data_request")
GRIEVANCE_STATUSES = ("open", "acknowledged", "resolved", "dismissed")
# What is no longer being worked on, and so what retention may delete.
CLOSED = ("resolved", "dismissed")

BODY_MIN, BODY_MAX = 10, 4000


class Grievance(Base):
    __tablename__ = "grievances"
    __table_args__ = (
        CheckConstraint(one_of("kind", GRIEVANCE_KINDS), name="ck_grievances_kind"),
        CheckConstraint(one_of("status", GRIEVANCE_STATUSES), name="ck_grievances_status"),
        CheckConstraint(
            f"length(btrim(body)) BETWEEN {BODY_MIN} AND {BODY_MAX}", name="ck_grievances_body"
        ),
        # Somebody has to be answerable: an account, or an address to write back to.
        CheckConstraint(
            "user_id IS NOT NULL OR reply_to IS NOT NULL", name="ck_grievances_reachable"
        ),
        # The account is the identity proof for a request about somebody's data.
        CheckConstraint(
            "kind <> 'data_request' OR user_id IS NOT NULL", name="ck_grievances_data_request_user"
        ),
        # A closed grievance says when, and an open one does not claim to have been.
        CheckConstraint(
            "(status IN ('resolved', 'dismissed')) = (resolved_at IS NOT NULL)",
            name="ck_grievances_closed",
        ),
        Index("ix_grievances_status_created", "status", "created_at"),
        Index("ix_grievances_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # What the sender is told and what they quote; unguessable, so it is a handle and not a way
    # to read anybody else's message (there is no lookup by reference).
    reference: Mapped[str] = mapped_column(unique=True)
    kind: Mapped[str] = mapped_column()
    body: Mapped[str] = mapped_column(Text)
    # CASCADE: a person's own message is their data, and erasing the account erases it (the
    # privacy service also deletes it explicitly, as it does every table).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None
    )
    # An email or a mobile number, by value, only for somebody who was not signed in. Never
    # mailed by us (see the service): the operator reads it to write back.
    reply_to: Mapped[str | None] = mapped_column(default=None)
    locale: Mapped[str] = mapped_column(default="en")
    status: Mapped[str] = mapped_column(default="open")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    resolution_note: Mapped[str | None] = mapped_column(Text, default=None)
    # SET NULL: an operator may exercise their own erasure and the record must outlive them.
    handled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
