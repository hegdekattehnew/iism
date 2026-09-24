"""The worker's entry point: `arq api.worker.WorkerSettings`.

**This module exists because of the order `arq`'s CLI does things in.**
`arq/cli.py` calls `import_string(worker_settings)` and *then*
`logging.config.dictConfig(default_log_config(verbose))`. So a
`configure_logging()` called at import time of `api/core/tasks.py` is imported,
runs, and is immediately clobbered -- arq installs its own `arq.standard`
StreamHandler with a `'%(asctime)s: %(message)s'` formatter and leaves
`propagate` untouched, so every worker line would then appear **twice**: once as
text through arq's handler, once as JSON through ours.

Configuring inside `on_startup` instead is the fix, because `on_startup` runs
after `dictConfig`. `WorkerSettings` below is otherwise `core.tasks`' own,
re-exported unchanged -- the tasks stay where they are; only the entry point
moves.

`Makefile`'s `worker` target points here, and **that is load-bearing for more
than logging**. The feature crons are registered *below*, in this composition
root, because `api/core/` must not import a feature module (ADR-014) -- so
pointing the Makefile back at `api.core.tasks.WorkerSettings` gives a worker
that starts cleanly, answers the health probe from the heartbeat, and silently
runs **none** of `drain_notifications`, `send_job_alerts` or
`close_expired_jobs`. No notification is ever sent, no candidate is alerted,
and a closing date never closes anything. This docstring used to say only that
the wrong entry point "restores the duplicate-line behaviour", which is true
and a long way short.

`tests/test_worker_schedule.py` is the guard, and it names what stops running.
"""

from typing import Any

from arq import cron

from api.core.logging import configure_logging, dict_config
from api.core.tasks import WorkerSettings as _Tasks
from api.core.tasks import publish_heartbeat
from api.modules.alerts.tasks import close_expired_jobs, send_job_alerts
from api.modules.analytics.tasks import purge_expired_analytics
from api.modules.notifications.tasks import drain_notifications

# Named on the command line as `arq --custom-log-dict api.worker.LOG_CONFIG`.
# arq applies exactly one logging config and it applies it *before* the worker
# starts, so this is the only way to catch the two lines it emits before any
# hook of ours can run.
LOG_CONFIG = dict_config()


async def _startup(ctx: dict[str, Any]) -> None:
    # First, and before anything else the worker does: arq's own dictConfig has
    # just run, and this is the earliest hook that comes after it.
    configure_logging()

    import structlog

    structlog.get_logger("iism.worker").info(
        "worker.started",
        functions=[f.__name__ if callable(f) else str(f) for f in _Tasks.functions],
        # arq's own "Starting worker for N functions" line is INFO on
        # `arq.worker`, which the logging config drops to WARNING to silence
        # the heartbeat. This replaces it, with more in it.
        #
        # `WorkerSettings.cron_jobs`, not `_Tasks.cron_jobs`: the crons
        # registered *here* are the ones arq runs, and counting the core list
        # reported "cron_jobs: 1" on a worker running two. Names, not a count,
        # so the line says which -- a number cannot be checked against what a
        # deployment was supposed to schedule.
        cron_jobs=[c.name for c in WorkerSettings.cron_jobs],
    )
    await publish_heartbeat(ctx)


class WorkerSettings:
    """arq's entry point. Identical to `core.tasks.WorkerSettings` but for
    `on_startup`, which is where logging gets configured."""

    functions = _Tasks.functions
    # Registered here, the composition root, rather than in `core/tasks.py`:
    # core must not import a feature module. 21:30 UTC is 03:00 in India.
    cron_jobs = [
        *_Tasks.cron_jobs,
        cron(purge_expired_analytics, hour={21}, minute={30}, run_at_startup=False),
        # Every minute: an application that arrives at 09:00 should not be
        # announced at 09:59. Cheap when the queue is empty -- one indexed
        # query returning nothing.
        cron(drain_notifications, minute=set(range(60)), run_at_startup=False),
        # Every five minutes. A vacancy published at 09:00 should reach the
        # people it matches that morning, not the next day -- and the sweep is
        # cheap when there is nothing new: one indexed query on `alerted_at`
        # returning no rows.
        cron(send_job_alerts, minute=set(range(0, 60, 5)), run_at_startup=False),
        # Hourly, on the hour. A closing date is a date, so being up to an hour
        # late costs nothing, and checking every minute would be a query per
        # minute forever to catch something that happens rarely.
        cron(close_expired_jobs, minute={0}, run_at_startup=False),
    ]
    on_startup = _startup
    redis_settings = _Tasks.redis_settings
    keep_result = _Tasks.keep_result
