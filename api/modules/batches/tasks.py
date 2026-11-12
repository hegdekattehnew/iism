"""The worker's half of the batch lifecycle (Sprint 101): the starting-soon reminders.

Registered at the composition root in `api/worker.py`, like the alert sweep, because `core/tasks.py`
must not import a feature module (ADR-014). It never raises: a cron that throws takes the worker's
next tick with it, and a reminder that misses a sweep goes out on the next.
"""

from typing import Any

import structlog

from api.core.database import get_sessionmaker

log = structlog.get_logger("iism.batches")


async def send_batch_reminders(ctx: dict[str, Any]) -> dict[str, int]:
    """Tell the learners of batches that start within three days, once."""
    from api.modules.batches.reminders import sweep

    try:
        async with get_sessionmaker()() as db:
            return await sweep(db)
    except Exception as error:  # noqa: BLE001 - a cron must not kill the worker
        log.warning("batches.reminders_failed", error=str(error)[:300])
        return {"batches": 0, "notices": 0}


async def send_reply_reminders(ctx: dict[str, Any]) -> dict[str, int]:
    """Remind each organisation, once, of learners who have waited past three days for a reply."""
    from api.modules.batches.reminders import sweep_replies

    try:
        async with get_sessionmaker()() as db:
            return await sweep_replies(db)
    except Exception as error:  # noqa: BLE001 - a cron must not kill the worker
        log.warning("batches.reply_reminders_failed", error=str(error)[:300])
        return {"organisations": 0, "emails": 0}
