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

`Makefile`'s `worker` target points here. Pointing it back at
`api.core.tasks.WorkerSettings` silently restores the duplicate-line behaviour,
which is why the settings class there is no longer the documented entrypoint.
"""

from typing import Any

from api.core.logging import configure_logging, dict_config
from api.core.tasks import WorkerSettings as _Tasks
from api.core.tasks import publish_heartbeat

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
        cron_jobs=len(_Tasks.cron_jobs),
    )
    await publish_heartbeat(ctx)


class WorkerSettings:
    """arq's entry point. Identical to `core.tasks.WorkerSettings` but for
    `on_startup`, which is where logging gets configured."""

    functions = _Tasks.functions
    cron_jobs = _Tasks.cron_jobs
    on_startup = _startup
    redis_settings = _Tasks.redis_settings
    keep_result = _Tasks.keep_result
