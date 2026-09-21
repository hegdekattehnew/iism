"""Scheduled analytics housekeeping, registered by `api/worker.py`."""

from typing import Any

import structlog

from api.core.config import get_settings
from api.core.database import get_sessionmaker
from api.modules.analytics.service import purge_expired

log = structlog.get_logger("iism.analytics")


async def purge_expired_analytics(ctx: dict[str, Any]) -> int:
    days = get_settings().analytics_retention_days
    async with get_sessionmaker()() as db:
        removed = await purge_expired(db, older_than_days=days)
    log.info("analytics.purged", removed=removed, retention_days=days)
    return removed
