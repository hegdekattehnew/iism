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

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base, one_of
from api.modules.identity import models as _identity_models  # noqa: F401 - the FK to users resolves against it

# Who it is for. A `tenant` recipient resolves to the organisation's contact
# address -- organisations have one, and their members may not all want it.
#
# `invitation` is the third because an invitee **may have no account**, so
# there is no user id to name. It points at the invitation row, which is the
# one table in the product that legitimately stores an address (see its
# docstring), and the rule below survives intact: this row still holds no
# address and still resolves one at send time. It also buys something storing
# the address would not -- revoking an invitation stops its mail.
RECIPIENT_KINDS = ("user", "tenant", "invitation")

# `in_app` is not a delivery channel so much as an absence of one: most
# candidates signed up with a phone, have no email, and SMS waits on DLT
# registration. It is what they get until then, and it is honest about that.
#
# A push (Sprint 65, ADR-075) is **not a channel of its own**: it is something the worker does *for*
# an in-app notice, once, when the person has a registered phone (`pushed_at` says it has been
# dealt with). Deciding that at the moment of queuing would put a query per notice on the request
# path, and a loop that queues a hundred (the alert sweep) would pay it a hundred times.
CHANNELS = ("email", "in_app")

# Closed, like every other set here. The template decides the words; the
# payload carries only what the words need.
TEMPLATES = (
    "application_received",
    "application_status_changed",
    # Sprint 24. The first thing a course provider is ever told.
    "course_interest_registered",
    # Sprint 25. The only message this product sends to somebody who may not
    # be a user yet.
    "organisation_invitation",
    # Sprint 27. The first message this product sends to somebody who did not
    # ask for it in the moment -- which is why it is the only one with an
    # opt-out (`CandidateProfile.job_alerts_enabled`).
    "job_alert",
    # Told to the applicants still waiting, never to the ones already answered.
    "vacancy_closed",
    # Sprint 41. A provider marked a learner's interest contacted or enrolled.
    # In-app only, by the owner's decision: free, and it reaches the phone-only
    # learner that an email never would.
    "course_interest_status_changed",
    # Sprint 41, ADR-048. An employer offered to sponsor the one standard a
    # candidate lacks for their vacancy. In-app only, and it names the
    # organisation, the standard and the course -- never anything about the
    # candidate, who has not yet chosen to be known to this employer.
    "sponsor_offer",
    # Sprint 43, BL-9.2. An operator granted or revoked an organisation's Verified
    # badge. Email to the organisation, never in-app: its members have no inbox to
    # read an in-app notice in. Sent only when the badge actually changes.
    "organisation_verified",
    "organisation_verification_revoked",
    # Sprint 44, BL-9.1. Somebody handed you an organisation. Email to the new
    # owner: becoming the person who can delete it should not be silent. A
    # phone-only account is `skipped`, as for every email here.
    "ownership_received",
    # Sprint 57, BL-14.3. A message somebody sent us was acknowledged, resolved or dismissed. In-app
    # only, to a signed-in sender: an anonymous sender has no recipient to resolve, and we never
    # write to an address a stranger typed into a form.
    "grievance_update",
    # Sprint 59, BL-14.4. An operator removed a listing, or put it back. Email to the
    # organisation, with the reason the operator wrote for it; never the reporter, who is not
    # named anywhere in the payload.
    "listing_removed",
    "listing_restored",
    # Sprint 60, BL-14.7. An employer moved an application and **left a message** (an interview
    # time and place, say). In-app and email, like a plain status change, but the payload says only
    # *that* there is one: the words are read from the application, never copied into the outbox,
    # which holds no free text that may carry a phone number.
    "application_status_message",
)

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
        # ...and what it actually wants (Sprint 50). In-app notices are never moved off `pending`
        # (only the email loop sets a status), so the index above makes every minute's tick walk
        # the whole in-app backlog to find a few email rows: 267 ms at 500,000 rows and growing
        # with every alert until the 90-day purge. This one holds only what the drain can send.
        Index(
            "ix_notifications_pending_email",
            "created_at",
            postgresql_where=text("status = 'pending' AND channel = 'email'"),
        ),
        # The push sweep's own query (Sprint 65): in-app notices to a person not yet dealt with.
        # Partial, so it holds only what is still owed (the sweep stamps every row it looks at,
        # phone or no phone), never the whole in-app backlog.
        Index(
            "ix_notifications_unpushed",
            "created_at",
            postgresql_where=text(
                "channel = 'in_app' AND recipient_kind = 'user' AND pushed_at IS NULL"
            ),
        ),
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
    # In-app, to a person only: when the push sweep dealt with this (sent it to their phones, or
    # found there was nothing to send, or gave up). `NULL` means "still owed a look" (ADR-075).
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# Closed, like every other set here; the database enforces it too (ck_device_token_platform).
DEVICE_PLATFORMS = ("android", "ios")


class DeviceToken(Base):
    """A phone that may be sent a push (Sprint 65, BL-15.6, ADR-075).

    **A token belongs to one person at a time.** Registering a token another account holds moves
    it: on a shared phone the last person to sign in is the one the next push is for. It is a
    person's data, so it is erased with the account (the foreign key cascades) and shown in their
    export (the platform and the dates; **never the token itself**, which is a credential to send
    to that phone).
    """

    __tablename__ = "device_tokens"
    __table_args__ = (
        CheckConstraint(one_of("platform", DEVICE_PLATFORMS), name="ck_device_token_platform"),
        Index("ix_device_tokens_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(Text, unique=True)
    platform: Mapped[str]
    locale: Mapped[str] = mapped_column(default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
