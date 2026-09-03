"""Dependency health checks backing /health/deep.

Each dependency is probed independently so the status page can show which one is
down rather than a single opaque red light.
"""

import time
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text

from api.core.cache import get_redis
from api.core.database import get_sessionmaker
from api.core.tasks import HEARTBEAT_KEY

Status = Literal["up", "down"]


class ComponentHealth(BaseModel):
    name: str
    status: Status
    latency_ms: float | None = None
    detail: str | None = None


class DeepHealth(BaseModel):
    status: Status
    environment: str
    version: str
    components: list[ComponentHealth]


async def check_database() -> ComponentHealth:
    started = time.perf_counter()
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
            version = await session.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
        return ComponentHealth(
            name="postgres",
            status="up",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            detail=f"pgvector {version}" if version else "pgvector NOT enabled",
        )
    except Exception as exc:
        return ComponentHealth(name="postgres", status="down", detail=str(exc)[:200])


async def check_redis() -> ComponentHealth:
    started = time.perf_counter()
    try:
        await get_redis().ping()
        return ComponentHealth(
            name="redis",
            status="up",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    except Exception as exc:
        return ComponentHealth(name="redis", status="down", detail=str(exc)[:200])


async def check_worker() -> ComponentHealth:
    """The worker publishes a heartbeat to Redis; absence means it is not running."""
    try:
        beat = await get_redis().get(HEARTBEAT_KEY)
    except Exception as exc:
        return ComponentHealth(name="worker", status="down", detail=str(exc)[:200])

    if beat is None:
        return ComponentHealth(name="worker", status="down", detail="no heartbeat in the last 20s")
    return ComponentHealth(name="worker", status="up", detail=f"last beat {beat}")
