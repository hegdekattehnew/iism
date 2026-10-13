"""The retention sweep, as an ARQ job (ADR-006)."""

from typing import Any

import structlog

from api.core.config import get_settings
from api.core.database import get_sessionmaker
from api.modules.grievances.service import purge_expired

log = structlog.get_logger("iism.grievances")


async def purge_expired_grievances(ctx: dict[str, Any]) -> int:
    days = get_settings().grievance_retention_days
    async with get_sessionmaker()() as db:
        removed = await purge_expired(db, retention_days=days)
    log.info("grievance.purged", retention_days=days, removed=removed)
    return removed
