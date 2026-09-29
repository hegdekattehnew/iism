"""The worker's half of the vacancy lifecycle.

Two crons, both here rather than in `core/tasks.py`: core must not import a
feature module (ADR-014), so they are registered at the composition root in
`api/worker.py` exactly as the analytics purge and the notification drain are.

Neither raises. A cron that throws takes the worker's next tick with it, and
these two are housekeeping -- an alert that misses one sweep goes out on the
next, and a vacancy that closes a minute late is a vacancy that closes.
"""

from typing import Any

import structlog

from api.core.database import get_sessionmaker

log = structlog.get_logger("iism.alerts")


async def send_job_alerts(ctx: dict[str, Any]) -> dict[str, int]:
    """Tell matched candidates about vacancies nobody has been told about."""
    from api.modules.alerts.service import sweep

    try:
        async with get_sessionmaker()() as db:
            result = await sweep(db)
            return result.__dict__
    except Exception as error:  # noqa: BLE001 - a cron must not kill the worker
        log.warning("alerts.sweep_failed", error=str(error)[:300])
        return {"jobs": 0, "alerts": 0}


async def close_expired_jobs(ctx: dict[str, Any]) -> dict[str, int]:
    """Close vacancies whose closing date has passed."""
    from api.modules.alerts.service import close_expired

    try:
        async with get_sessionmaker()() as db:
            return {"closed": await close_expired(db)}
    except Exception as error:  # noqa: BLE001 - a cron must not kill the worker
        log.warning("alerts.expiry_failed", error=str(error)[:300])
        return {"closed": 0}
