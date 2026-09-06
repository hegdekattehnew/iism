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
from typing import Any

import structlog
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
    if name not in EVENT_NAMES:  # pragma: no cover - guarded by the caller and a CHECK
        log.warning("analytics.unknown_event", event=name)
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
        log.exception("analytics.record_failed", event=name)
        # Leave the session usable for whatever the handler does next.
        await db.rollback()
