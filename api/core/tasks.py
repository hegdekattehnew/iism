"""Async task plumbing (ADR-006, ADR-027).

ARQ rather than Celery: this application is async end to end, and ARQ shares the
app's existing session machinery instead of demanding a parallel sync engine.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from arq import cron
from arq.connections import ArqRedis, RedisSettings, create_pool

from api.core.config import get_settings

# Worker liveness is published here and read by /health/deep. TTL is longer than
# the heartbeat interval so a single missed beat does not report a false outage.
HEARTBEAT_KEY = "iism:worker:heartbeat"
HEARTBEAT_TTL_SECONDS = 20


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


_pool: ArqRedis | None = None


async def get_task_pool() -> ArqRedis:
    """Connection pool used by the API to enqueue jobs."""
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def close_task_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
    _pool = None


# ----------------------------------------------------------------- tasks


async def ping(ctx: dict[str, Any], note: str = "") -> dict[str, Any]:
    """Deliberately trivial task, used to prove the async path end to end.

    Sleeps briefly so the queued -> in-progress -> complete transition is
    actually visible in the UI rather than finishing before the first poll.
    """
    await asyncio.sleep(1.5)
    return {
        "pong": True,
        "note": note,
        "worker_job_id": ctx.get("job_id"),
        "completed_at": datetime.now(UTC).isoformat(),
    }


async def publish_heartbeat(ctx: dict[str, Any]) -> None:
    redis: ArqRedis = ctx["redis"]
    await redis.set(HEARTBEAT_KEY, datetime.now(UTC).isoformat(), ex=HEARTBEAT_TTL_SECONDS)


async def _startup(ctx: dict[str, Any]) -> None:
    await publish_heartbeat(ctx)


class WorkerSettings:
    """Entrypoint: `arq api.core.tasks.WorkerSettings`."""

    functions = [ping]  # noqa: RUF012
    cron_jobs = [  # noqa: RUF012
        cron(publish_heartbeat, second=set(range(0, 60, 5)), run_at_startup=True)
    ]
    on_startup = _startup
    redis_settings = redis_settings()
    keep_result = 300
