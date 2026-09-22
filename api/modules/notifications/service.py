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
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update
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
    pending = (
        await db.scalars(
            select(Notification)
            .where(Notification.status == "pending", Notification.channel == "email")
            .order_by(Notification.created_at)
            .limit(limit)
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
