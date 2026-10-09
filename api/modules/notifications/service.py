"""Queue a notification, and drain the queue.

Two rules, both learned elsewhere in this project:

- **Queue inside the request, send outside it** (ADR-006). A delivery failure
  must never be able to fail the thing it is describing -- an SMTP timeout
  while somebody applies for a job would otherwise lose the application.
- **The address is resolved here, at send time**, never stored on the row: it
  keeps contact details out of a dumped table and out of any log line, and it
  is correct when somebody changes their address between queue and send.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.notifications import get_email_provider
from api.core.config import get_settings
from api.modules.identity.models import Invitation, Membership, Tenant, User
from api.modules.notifications.models import Notification
from api.modules.notifications.templates import render

log = structlog.get_logger("iism.notifications")

# How many times a failure is worth retrying before it is somebody's problem
# rather than the queue's.
MAX_ATTEMPTS = 5


async def enqueue(
    db: AsyncSession,
    *,
    recipient_kind: str,
    recipient_id: uuid.UUID,
    channel: str,
    template: str,
    payload: dict[str, Any],
    locale: str = "en",
) -> Notification:
    """Record what is owed. Does not commit -- the caller owns the transaction."""
    notification = Notification(
        recipient_kind=recipient_kind,
        recipient_id=recipient_id,
        channel=channel,
        template=template,
        payload=payload,
        locale=locale,
    )
    db.add(notification)
    return notification


async def enqueue_many(db: AsyncSession, notices: Sequence[Mapping[str, Any]]) -> int:
    """Record what is owed to many people, without building one ORM object each.

    Each notice carries the same keys `enqueue` takes (`locale` optional). Does not commit.
    Erasing an organisation with thousands of waiting applicants used to build one ORM object per
    applicant (Sprint 50's audit); this writes the same rows as batched multi-row INSERTs (the
    driver's own limit on bind parameters is respected by SQLAlchemy's batching).
    """
    if not notices:
        return 0
    await db.execute(
        insert(Notification),
        [{"locale": "en", **notice} for notice in notices],
    )
    return len(notices)


async def _address_for(db: AsyncSession, notification: Notification) -> str | None:
    """Where to send, resolved now rather than stored when queued.

    **An organisation's contact address is usually empty.** Registration puts
    the address on the `User` who registered; `Tenant.contact_email` is filled
    in later, on the organisation profile, and most never are. Falling back to
    the owner is what makes this reach a person -- the first test written here
    failed on exactly that, with every employer notification silently skipped.

    The fallback is deliberately not "copy the registrant's address into
    `contact_email`": that field is the organisation's stated inbox, shown to
    its members, and filling it in on somebody's behalf publishes a personal
    address they never offered.
    """
    if notification.recipient_kind == "invitation":
        # The one recipient that may not be a user yet. Resolving through the
        # row rather than storing the address is what makes a **revoked**
        # invitation stop sending: `skipped`, not `sent`, with nothing
        # delivered to somebody whose offer was withdrawn before the drain ran.
        invitation = await db.get(Invitation, notification.recipient_id)
        if invitation is None:
            return None
        return invitation.email if invitation.is_open(datetime.now(UTC)) else None
    if notification.recipient_kind == "tenant":
        tenant = await db.get(Tenant, notification.recipient_id)
        if tenant is None:
            return None
        if tenant.contact_email:
            return tenant.contact_email
        owner = await db.scalar(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.tenant_id == tenant.id,
                Membership.role == "owner",
                User.email.isnot(None),
            )
            .order_by(User.created_at)
            .limit(1)
        )
        return owner.email if owner is not None else None
    user = await db.get(User, notification.recipient_id)
    return user.email if user is not None else None


async def drain(db: AsyncSession, *, limit: int = 50) -> dict[str, int]:
    """Send what is pending. Returns a count per outcome.

    `skipped` is not `failed`: a candidate who signed up with a phone has no
    email address, and there is nothing wrong with that -- the in-app copy is
    what reaches them until DLT registration makes SMS possible.
    """
    # Locked until the commit below, and rows another tick already holds are
    # skipped rather than waited for. Without it a tick that outlived its
    # minute (a slow SMTP batch) and the next one picked the same rows and
    # sent each message twice. A crash mid-batch still resends, because the
    # status commit is the last step: at-least-once, never twice at once.
    pending = (
        await db.scalars(
            select(Notification)
            .where(Notification.status == "pending", Notification.channel == "email")
            .order_by(Notification.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()

    counts = {"sent": 0, "skipped": 0, "failed": 0}
    provider = get_email_provider()
    base = get_settings().web_base_url

    for notification in pending:
        address = await _address_for(db, notification)
        if not address:
            notification.status = "skipped"
            notification.last_error = "no address on file"
            counts["skipped"] += 1
            continue

        subject, body = render(
            notification.template,
            notification.locale,
            {**notification.payload, "link": f"{base}{notification.payload.get('path', '/')}"},
        )
        notification.attempts += 1
        try:
            await provider.send_email(address, subject, body)
        except Exception as error:  # noqa: BLE001 - every provider failure is the same here
            # Never the address in the log line: the whole point of resolving it
            # at send time is that it does not get written down (ADR-023).
            notification.last_error = str(error)[:500]
            notification.status = "failed" if notification.attempts >= MAX_ATTEMPTS else "pending"
            counts["failed"] += 1
            log.warning(
                "notification.send_failed",
                template=notification.template,
                attempts=notification.attempts,
                terminal=notification.status == "failed",
            )
            continue

        notification.status = "sent"
        notification.sent_at = datetime.now(UTC)
        counts["sent"] += 1

    await db.commit()
    if any(counts.values()):
        log.info("notification.drained", **counts)
    return counts


async def unread_for(db: AsyncSession, user_id: uuid.UUID) -> list[Notification]:
    """The candidate's in-app notices, newest first."""
    rows = await db.scalars(
        select(Notification)
        .where(
            Notification.recipient_kind == "user",
            Notification.recipient_id == user_id,
            Notification.channel == "in_app",
        )
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    return list(rows.all())


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(
            Notification.recipient_kind == "user",
            Notification.recipient_id == user_id,
            Notification.channel == "in_app",
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def purge_expired(db: AsyncSession, *, retention_days: int) -> dict[str, int]:
    """Delete what is past its retention, and nothing that is still owed or unseen.

    The outbox is the one table that keeps what the product *said* to a person, and
    nothing ever removed a row: an email delivered in 2026 would sit, with its payload
    -- a vacancy title, an organisation's name -- for as long as the database does. Data
    kept "just in case" is data held without a purpose (DPDP Act 2023), which is the
    reason the analytics events already have a purge (`analytics.purge_expired`).

    Three classes, counted separately so the log says which:

    * **delivered** -- an email that was `sent`, `skipped` or terminally `failed`, older
      than `retention_days`. A `pending` row is never touched, however old: it is still
      owed, and the drain will either send it or fail it.
    * **read** -- an in-app notice the person opened, older than `retention_days`.
    * **unread** -- an in-app notice nobody opened, kept **twice** as long. The list
      shows the newest fifty regardless of age, and an unopened notice may be an offer
      to sponsor a standard (ADR-048) that the person has not yet seen.

    Age is `created_at`, not `sent_at`, because a skipped row has no `sent_at`.
    """
    now = func.now()
    delivered = await db.execute(
        delete(Notification).where(
            Notification.channel == "email",
            Notification.status.in_(("sent", "skipped", "failed")),
            Notification.created_at < now - timedelta(days=retention_days),
        )
    )
    read = await db.execute(
        delete(Notification).where(
            Notification.channel == "in_app",
            Notification.read_at.is_not(None),
            Notification.created_at < now - timedelta(days=retention_days),
        )
    )
    unread = await db.execute(
        delete(Notification).where(
            Notification.channel == "in_app",
            Notification.read_at.is_(None),
            Notification.created_at < now - timedelta(days=2 * retention_days),
        )
    )
    await db.commit()
    return {
        "delivered": int(getattr(delivered, "rowcount", 0) or 0),
        "read": int(getattr(read, "rowcount", 0) or 0),
        "unread": int(getattr(unread, "rowcount", 0) or 0),
    }
