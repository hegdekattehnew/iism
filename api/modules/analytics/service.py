"""Recording events, and the two rules that matter.

**Never break the request.** An analytics failure must not take down a page: a
broken metric is a smaller problem than a candidate who cannot see their
matches. Every write here is best-effort and nothing raises.

**`record` commits.** `get_db_session` never commits -- it only rolls back on
error -- so an event that is merely flushed is discarded when the request ends,
which is exactly what happened the first time this was wired up: three `record`
calls per request and an empty table. The consequence is that `record` must be
called from a handler with no other uncommitted work, or after that work has
been committed. Every current caller is a read endpoint.
"""

import uuid
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics.models import EVENT_NAMES, AnalyticsEvent

log = structlog.get_logger(__name__)


async def record(
    db: AsyncSession,
    name: str,
    *,
    user_id: uuid.UUID | None = None,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Record one event. Never raises."""
    if name not in EVENT_NAMES:
        # `event_name`, not `event`: structlog's bound logger takes the first
        # positional argument as `event`, so an `event=` keyword collides with
        # it and raises TypeError -- out of a function documented never to
        # raise, and from above the try/except that would otherwise absorb it.
        # A test asserts an unknown name is dropped rather than raised.
        log.warning("analytics.unknown_event", event_name=name)
        return
    try:
        db.add(
            AnalyticsEvent(
                name=name,
                user_id=user_id,
                subject_type=subject_type,
                subject_id=subject_id,
                payload=payload,
            )
        )
        # Commit, not flush: the request session is never committed for us, so
        # a flushed event is thrown away when the request ends.
        await db.commit()
    except Exception:  # pragma: no cover - defensive by design
        # Swallowed on purpose: measurement must never be the reason a page
        # fails. The exception is logged, not raised.
        log.exception("analytics.record_failed", event_name=name)
        # Leave the session usable for whatever the handler does next.
        await db.rollback()


async def record_many(
    db: AsyncSession,
    events: "Sequence[tuple[str, dict[str, Any]]]",
) -> None:
    """Record several events in **one** commit. Never raises.

    `record()` commits, which is right for one event and wrong for five: a
    match-detail view recommends up to five courses, and looping `record()`
    would put five commits on a hot read path. Same contract otherwise --
    unknown names are dropped with a warning, failures are swallowed, and
    measurement is never the reason a page fails.

    Each event is `(name, fields)` where `fields` holds any of `user_id`,
    `subject_type`, `subject_id`, `payload`.
    """
    rows = []
    for name, fields in events:
        if name not in EVENT_NAMES:
            log.warning("analytics.unknown_event", event_name=name)
            continue
        rows.append(AnalyticsEvent(name=name, **fields))
    if not rows:
        return
    try:
        db.add_all(rows)
        await db.commit()
    except Exception:  # pragma: no cover - defensive by design
        log.exception("analytics.record_many_failed", count=len(rows))
        await db.rollback()


async def purge_expired(db: AsyncSession, *, older_than_days: int) -> int:
    """Delete events older than the retention period. Returns how many went.

    Events carry no name, phone or email, but they are tied to an account, and
    data kept "in case" is data held without a purpose (DPDP Act 2023). Nothing
    ever deleted them before.
    """
    result = await db.execute(
        delete(AnalyticsEvent).where(
            AnalyticsEvent.occurred_at < func.now() - timedelta(days=older_than_days)
        )
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
