"""Async task plumbing (ADR-006, ADR-027).

ARQ rather than Celery: this application is async end to end, and ARQ shares the
app's existing session machinery instead of demanding a parallel sync engine.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from arq import cron
from arq.connections import ArqRedis, RedisSettings, create_pool
from arq.jobs import Job, JobStatus

from api.core.config import get_settings

log = structlog.get_logger("iism.tasks")

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


async def enqueue_ping(note: str = "") -> str:
    """Put a demonstration job on the queue and return its id.

    Here rather than in the route because talking to the queue is this module's
    job -- `api/main.py` held the only two handlers in the product with no
    service behind them at all.
    """
    pool = await get_task_pool()
    job = await pool.enqueue_job("ping", note)
    if job is None:  # pragma: no cover - only on a duplicate job id
        raise RuntimeError("could not enqueue job")
    return job.job_id


async def task_result(job_id: str) -> tuple[str, dict[str, Any] | None]:
    """A queued job's status, and its result once there is one.

    The result is fetched only for a completed job, and a failure to fetch it is
    **logged and swallowed**: a demonstration endpoint must not 500 because a
    result expired out of Redis. It is logged because a job that *raised* is
    otherwise indistinguishable here from one that returned nothing, and for two
    sprints there was no line anywhere saying which had happened.
    """
    pool = await get_task_pool()
    job = Job(job_id, pool)
    state = await job.status()
    if state is not JobStatus.complete:
        return state.value, None
    try:
        return state.value, await job.result(timeout=1)
    except Exception:
        log.warning("tasks.result_unavailable", job_id=job_id, exc_info=True)
        return state.value, None


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
