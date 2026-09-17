"""The outbox: what we owe someone, and whether it has been delivered.

Sprint 21 closed the loop and told nobody -- an application arrived and the
employer learned about it only by opening a page they had no reason to open.
This is the queue that fixes that, and it is a table rather than a direct send
because delivery must never be able to fail a request (ADR-006): an SMTP
timeout while someone is applying for a job would lose the application.

**The row names a recipient; it does not hold their address.** The email is
resolved at send time from the account or the organisation. That keeps contact
details out of a table that is dumped, out of any log line that renders a row,
and correct when someone changes their address between queueing and sending.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of

# Who it is for. A `tenant` recipient resolves to the organisation's contact
# address -- organisations have one, and their members may not all want it.
RECIPIENT_KINDS = ("user", "tenant")

# `in_app` is not a delivery channel so much as an absence of one: most
# candidates signed up with a phone, have no email, and SMS waits on DLT
# registration. It is what they get until then, and it is honest about that.
CHANNELS = ("email", "in_app")

# Closed, like every other set here. The template decides the words; the
# payload carries only what the words need.
TEMPLATES = ("application_received", "application_status_changed")

STATUSES = ("pending", "sent", "failed", "skipped")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            one_of("recipient_kind", RECIPIENT_KINDS), name="ck_notification_recipient"
        ),
        CheckConstraint(one_of("channel", CHANNELS), name="ck_notification_channel"),
        CheckConstraint(one_of("template", TEMPLATES), name="ck_notification_template"),
        CheckConstraint(one_of("status", STATUSES), name="ck_notification_status"),
        # The drain's own query: oldest pending first.
        Index("ix_notifications_pending", "status", "created_at"),
        # The candidate's unread list.
        Index("ix_notifications_recipient", "recipient_kind", "recipient_id", "read_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipient_kind: Mapped[str]
    recipient_id: Mapped[uuid.UUID]
    channel: Mapped[str]
    template: Mapped[str]
    # What the words need -- a vacancy title, a status. Never a name, phone or
    # email: those are resolved when the message is built.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    locale: Mapped[str] = mapped_column(default="en")

    status: Mapped[str] = mapped_column(default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # In-app only: when the person actually looked at it.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
