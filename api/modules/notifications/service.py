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
from sqlalchemy import delete, func, insert, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.notifications import get_email_provider
from api.adapters.push import InvalidDeviceToken, get_push_provider
from api.core.config import get_settings
from api.modules.identity.models import Invitation, Membership, Tenant, User
from api.modules.notifications.models import DeviceToken, Notification
from api.modules.notifications.templates import push_data, push_text, render

log = structlog.get_logger("iism.notifications")

# How many times a failure is worth retrying before it is somebody's problem
# rather than the queue's.
MAX_ATTEMPTS = 5

# `IN (...)` lists are chunked: asyncpg refuses a statement with more than 32,767 bind parameters.
_CHUNK = 5000

# A notice older than this is not worth a lock-screen alert: the worker was down, or the person had
# no phone then. The sweep stamps it as dealt with and sends nothing, so switching push on never
# replays a backlog (the alert sweep's `alerted_at` lesson, Sprint 27).
PUSH_WINDOW = timedelta(hours=24)
# How many notices one tick looks at. Larger than the email batch because a notice for a person
# with no phone costs one stamp: a hundred-candidate alert sweep must not queue phones behind them.
PUSH_BATCH = 500


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

    pushed = await _sweep_push(db, limit=PUSH_BATCH)

    await db.commit()
    if any(counts.values()):
        log.info("notification.drained", **counts)
    if pushed["sent"] or pushed["failed"]:
        log.info("notification.pushed", **pushed)
    return counts


async def _sweep_push(db: AsyncSession, *, limit: int) -> dict[str, int]:
    """Send a push for each in-app notice to a person that has not been looked at yet (ADR-075).

    **The sweep stamps every row it looks at** (`pushed_at`), whether or not there was anything to
    send, so the partial index it reads holds only what is still owed and a person with no phone
    costs one stamp, not a retry for ever. It is not part of the email counts: most in-app notices
    go to people with no phone, and counting each as "skipped" would bury the email figures.

    The tokens are resolved here and never stored on a row, for the reason an address is. The words
    come from a fixed table keyed by template and language and **nothing in the payload reaches
    the title, the body or the data** beyond an in-app path: a push is shown on a lock screen and
    kept by the operating system. A token the provider says is dead is deleted, so a phone that
    left is not held about for no purpose. A failure retries (`attempts`) and gives up after
    `MAX_ATTEMPTS`.
    """
    pending = (
        await db.scalars(
            select(Notification)
            .where(
                Notification.channel == "in_app",
                Notification.recipient_kind == "user",
                Notification.pushed_at.is_(None),
            )
            .order_by(Notification.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    counts = {"sent": 0, "failed": 0}
    if not pending:
        return counts

    devices: dict[uuid.UUID, list[DeviceToken]] = {}
    for start in range(0, len(pending), _CHUNK):
        chunk = pending[start : start + _CHUNK]
        rows = await db.scalars(
            select(DeviceToken).where(DeviceToken.user_id.in_({n.recipient_id for n in chunk}))
        )
        for device in rows.all():
            devices.setdefault(device.user_id, []).append(device)

    now = datetime.now(UTC)
    provider = get_push_provider()
    for notification in pending:
        words = push_text(notification.template, notification.locale)
        phones = devices.get(notification.recipient_id, [])
        if words is None or not phones or now - notification.created_at > PUSH_WINDOW:
            notification.pushed_at = now
            continue

        notification.attempts += 1
        delivered, failure = 0, None
        for device in phones:
            try:
                await provider.send_push(
                    device.token,
                    words[0],
                    words[1],
                    push_data(notification.template, notification.payload),
                )
                delivered += 1
            except InvalidDeviceToken:
                await db.delete(device)
            except Exception as error:  # noqa: BLE001 - every provider failure is the same here
                failure = str(error)[:500]
        if delivered:
            notification.pushed_at = now
            counts["sent"] += 1
        elif failure is not None:
            notification.last_error = failure
            counts["failed"] += 1
            log.warning(
                "push.send_failed", template=notification.template, attempts=notification.attempts
            )
            if notification.attempts >= MAX_ATTEMPTS:
                notification.pushed_at = now  # gave up: the in-app notice is still there
        else:
            notification.pushed_at = now  # every phone was dead, and has been forgotten
    return counts


async def list_for(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    before: datetime | None = None,
    before_id: uuid.UUID | None = None,
) -> list[Notification]:
    """A person's in-app notices, newest first, read ones included.

    (Named `unread_for` until Sprint 60, though it never filtered.) The cursor is the last
    notice's `(created_at, id)`: **both**, because `created_at` is the transaction's time and an
    alert sweep or an erasure queues hundreds of notices in one transaction with the *same*
    timestamp. A cursor on time alone would skip every one of them past the page boundary.
    """
    query = select(Notification).where(
        Notification.recipient_kind == "user",
        Notification.recipient_id == user_id,
        Notification.channel == "in_app",
    )
    if before is not None and before_id is not None:
        query = query.where(tuple_(Notification.created_at, Notification.id) < (before, before_id))
    elif before is not None:
        query = query.where(Notification.created_at < before)
    rows = await db.scalars(
        query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    )
    return list(rows.all())


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """How many in-app notices this person has not opened: what the header's count shows."""
    return (
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_kind == "user",
                Notification.recipient_id == user_id,
                Notification.channel == "in_app",
                Notification.read_at.is_(None),
            )
        )
    ) or 0


async def mark_read(db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    """Open one notice. `False` when it is not this person's, which the route answers with a 404:
    a notice's existence is not news to anyone but its recipient."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_kind == "user",
            Notification.recipient_id == user_id,
            Notification.channel == "in_app",
        )
        .values(read_at=func.coalesce(Notification.read_at, func.now()))
    )
    await db.commit()
    return bool(getattr(result, "rowcount", 0))


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
