"""The retention sweep, as an ARQ job (ADR-006)."""

from typing import Any

import structlog

from api.core.config import get_settings
from api.core.database import get_sessionmaker
from api.modules.moderation.service import purge_expired

log = structlog.get_logger("iism.moderation")


async def purge_expired_reports(ctx: dict[str, Any]) -> int:
    days = get_settings().report_retention_days
    async with get_sessionmaker()() as db:
        removed = await purge_expired(db, retention_days=days)
    log.info("moderation.purged", retention_days=days, removed=removed)
    return removed
