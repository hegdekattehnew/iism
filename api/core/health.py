"""Dependency health checks backing /health/deep.

Each dependency is probed independently so the status page can show which one is
down rather than a single opaque red light.
"""

import sys
import time
from typing import Literal

import structlog
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


log = structlog.get_logger("iism.health")


def _reason() -> str:
    """The current exception's message, bounded. Called from an `except`."""
    exc = sys.exc_info()[1]
    return str(exc)[:200] if exc else "unknown"


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
    except Exception:
        # Logged, not merely returned. This is the dependency-failure detector,
        # and it used to discard the reason the instant the response was sent:
        # an outage at 3am left no trace anywhere. `detail` still carries the
        # message to the caller; the redaction filter scrubs the DSN out of
        # both, which is why `str(exc)` is safe to keep.
        log.exception("health.check_failed", component="postgres")
        return ComponentHealth(name="postgres", status="down", detail=_reason())


async def check_redis() -> ComponentHealth:
    started = time.perf_counter()
    try:
        await get_redis().ping()
        return ComponentHealth(
            name="redis",
            status="up",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    except Exception:
        # Logged, not merely returned. This is the dependency-failure detector,
        # and it used to discard the reason the instant the response was sent:
        # an outage at 3am left no trace anywhere. `detail` still carries the
        # message to the caller; the redaction filter scrubs the DSN out of
        # both, which is why `str(exc)` is safe to keep.
        log.exception("health.check_failed", component="redis")
        return ComponentHealth(name="redis", status="down", detail=_reason())


async def check_worker() -> ComponentHealth:
    """The worker publishes a heartbeat to Redis; absence means it is not running."""
    try:
        beat = await get_redis().get(HEARTBEAT_KEY)
    except Exception:
        # Logged, not merely returned. This is the dependency-failure detector,
        # and it used to discard the reason the instant the response was sent:
        # an outage at 3am left no trace anywhere. `detail` still carries the
        # message to the caller; the redaction filter scrubs the DSN out of
        # both, which is why `str(exc)` is safe to keep.
        log.exception("health.check_failed", component="worker")
        return ComponentHealth(name="worker", status="down", detail=_reason())

    if beat is None:
        log.warning("health.worker_missing", component="worker")
        return ComponentHealth(name="worker", status="down", detail="no heartbeat in the last 20s")
    return ComponentHealth(name="worker", status="up", detail=f"last beat {beat}")
