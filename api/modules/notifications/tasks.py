"""The drain, as an ARQ job (ADR-006)."""

from typing import Any

import structlog

from api.core.config import get_settings
from api.core.database import get_sessionmaker
from api.modules.notifications.service import drain, purge_expired

log = structlog.get_logger("iism.notifications")


async def drain_notifications(ctx: dict[str, Any]) -> dict[str, int]:
    async with get_sessionmaker()() as db:
        return await drain(db)


async def purge_expired_notifications(ctx: dict[str, Any]) -> dict[str, int]:
    days = get_settings().notification_retention_days
    async with get_sessionmaker()() as db:
        removed = await purge_expired(db, retention_days=days)
    log.info("notification.purged", retention_days=days, **removed)
    return removed
