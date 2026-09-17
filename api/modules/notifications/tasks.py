"""The drain, as an ARQ job (ADR-006)."""

from typing import Any

import structlog

from api.core.database import get_sessionmaker
from api.modules.notifications.service import drain

log = structlog.get_logger("iism.notifications")


async def drain_notifications(ctx: dict[str, Any]) -> dict[str, int]:
    async with get_sessionmaker()() as db:
        return await drain(db)
