"""Process-wide logging: one JSON object per line, on stdout.

Before this module there were **three uncorrelated sinks in one process**:
structlog's default `PrintLogger` writing ANSI-coloured text to stdout, an
unconfigured `logging.getLogger("iism.notifications")` falling through to the
stdlib's `lastResort` handler (WARNING-only, stderr, no timestamp, no logger
name), and Starlette's unhandled tracebacks raw to stderr. Nothing joined them,
nothing was machine-readable, and no line carried a request id.

The bridge is `structlog.stdlib.ProcessorFormatter`. structlog's own chain ends
by handing the event dict to stdlib `logging` (`wrap_for_formatter`) instead of
rendering it, and the formatter on the single root handler renders *both*
origins through one shared tail. uvicorn, arq, SQLAlchemy and the notification
adapters land in the same stream, with the same keys, as `log.info("http.request")`.

Three chains, and the split is the whole design:

  * `structlog.configure(processors=...)`  -- structlog-native records only
  * `ProcessorFormatter(foreign_pre_chain=...)` -- stdlib records only
  * `ProcessorFormatter(processors=...)`   -- **both**, and therefore the only
    place the redaction filter can sit and be unbypassable.

Call `configure_logging()` exactly once per process, as early as possible:
`api/main.py` for the API and `api/worker.py` for the worker. It is idempotent,
so a reload worker or a test fixture can call it again without stacking
handlers.
"""

import logging
import sys
from logging.config import dictConfig
from typing import Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from api.core.config import get_settings
from api.core.redaction import RedactingProcessor

_configured = False


def _drop_uvicorn_colour(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    """uvicorn attaches `color_message` -- the same text with ANSI escapes --
    as a LogRecord extra. `ExtraAdder` lifts it faithfully, which puts escape
    codes in a JSON field nobody will ever read."""
    event_dict.pop("color_message", None)
    return event_dict


def _enrichment(*, native: bool) -> list[Processor]:
    """The keys every record carries, whatever produced it.

    Deliberately built twice -- once for the native chain and once for
    `foreign_pre_chain` -- because `ProcessorFormatter` runs exactly one of the
    two per record, never both.
    """
    chain: list[Processor] = []
    if native:
        # First, so a DEBUG record under an INFO logger costs one comparison
        # rather than a contextvar merge and a timestamp.
        chain.append(structlog.stdlib.filter_by_level)
    chain += [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        # `level` is a string, which CloudWatch Insights cannot compare
        # ordinally. `level_number` is what makes `filter level_number >= 40`
        # -- the query you will actually write -- possible.
        structlog.stdlib.add_log_level_number,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    if native:
        # For `log.info("sent %s", x)`. Foreign records are already
        # interpolated by ProcessorFormatter via `record.getMessage()`.
        chain.insert(-1, structlog.stdlib.PositionalArgumentsFormatter())
    else:
        # Lifts `extra={...}` off the LogRecord -- arq passes one on job
        # failure. Unvetted third-party content, which is exactly why the
        # redactor sits downstream of this.
        chain.insert(2, structlog.stdlib.ExtraAdder())
        chain.insert(3, _drop_uvicorn_colour)
    return chain


def build_tail(log_format: str) -> list[Processor]:
    """The shared tail: everything both origins pass through.

    Exported so the tests can format records through the very processor list
    `dictConfig` installs, rather than through a handler -- pytest's logging
    plugin swaps handlers out, so a StreamHandler capture comes back empty and
    every assertion against it passes vacuously.
    """
    tail: list[Processor] = [
        # Must be first: strips `_record` and `_from_structlog`, which the
        # redactor would otherwise walk (and the renderer would emit).
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
    ]
    if log_format == "json":
        tail.append(
            structlog.processors.ExceptionRenderer(
                structlog.processors.ExceptionDictTransformer(
                    # NOT `structlog.processors.dict_tracebacks`, whose
                    # transformer defaults to `show_locals=True`. That
                    # serialises every frame's locals -- and `code =
                    # generate_otp()` is a plain local in four functions in
                    # `api/modules/identity/service.py`. A raise anywhere under
                    # those would write a live OTP into the log. ADR-023
                    # forbids it and the redactor should not be the only thing
                    # standing between us and it.
                    show_locals=False,
                )
            )
        )
    else:
        tail.append(structlog.dev.set_exc_info)

    tail += [
        # Last mutating step before the renderer, and the reason this list
        # exists: sitting here it runs on every structlog BoundLogger *and*
        # every `logging.getLogger()` call in the process, on merged
        # contextvars, on lifted `extra`, and on the rendered exception.
        RedactingProcessor(),
    ]

    if log_format == "json":
        tail.append(structlog.processors.JSONRenderer())
    else:
        tail.append(structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()))
    return tail


def dict_config() -> dict[str, Any]:
    """The config as a plain dict, for `arq --custom-log-dict`.

    arq's CLI applies exactly one logging config, *before* the worker starts:
    its own `default_log_config`, or whatever this returns if it is named on
    the command line. Handing it ours is what stops arq's first two lines
    ("Starting worker for N functions", the redis version banner) escaping as
    text -- they are emitted before `on_startup`, so no hook can catch them.
    """
    settings = get_settings()
    return _dict_config(settings.log_level.upper(), settings.log_format)


def _dict_config(level: str, log_format: str) -> dict[str, Any]:
    return {
        "version": 1,
        # uvicorn and arq both configure their own loggers. Without this, this
        # config would be applied *beside* theirs and every line would appear
        # twice -- once as text through their handler, once as JSON through
        # ours.
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": build_tail(log_format),
                "foreign_pre_chain": _enrichment(native=False),
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                # stdout, not stderr. Under `awslogs` both are collected, but
                # keeping one stream keeps ordering meaningful.
                "stream": "ext://sys.stdout",
            }
        },
        "root": {"handlers": ["default"], "level": level},
        "loggers": {
            # uvicorn installs its *own* handlers via its own `dictConfig`,
            # which runs after this module is imported -- so these three entries
            # must name `handlers` explicitly. `logging.config` only clears a
            # logger's existing handlers when the key is present; omitting it
            # leaves uvicorn's text handler attached and every line appears
            # twice, once as text and once as JSON.
            #
            # `configure_logging()` is also called again from the lifespan
            # startup, which runs after uvicorn has finished configuring.
            "uvicorn": {"handlers": [], "propagate": True},
            "uvicorn.error": {"handlers": [], "level": "INFO", "propagate": True},
            # The access log duplicates `http.request` from our own middleware
            # and carries less: no duration, no request id, no user, and the
            # interpolated path rather than the route template.
            "uvicorn.access": {"handlers": [], "propagate": False},
            # The heartbeat cron logs two INFO lines every five seconds --
            # ~34,500 lines a day. At WARNING what survives is exactly the set
            # worth keeping: a job raised (ERROR), max retries exceeded, job
            # expired, function not found, deserialisation failed.
            "arq.worker": {"level": "WARNING", "propagate": True},
            # Declared with a handler so `sqlalchemy/log.py` sees
            # `self.logger.handlers` non-empty and does *not* attach its own
            # raw StreamHandler, which would bypass the redactor and print
            # bound parameters. `DB_ECHO` is refused outside development too.
            "sqlalchemy.engine.Engine": {
                "handlers": ["default"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }


def configure_logging() -> None:
    """Idempotent. Call once per process, before anything logs."""
    global _configured
    settings = get_settings()
    level = settings.log_level.upper()

    dictConfig(_dict_config(level, settings.log_format))

    structlog.configure(
        processors=[
            *_enrichment(native=True),
            # Terminates the native chain: hand off to stdlib rather than
            # render, so both origins converge on one formatter.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # False, so `configure_logging()` called twice (reload, tests) replaces
        # the configuration rather than being ignored the second time.
        cache_logger_on_first_use=False,
    )
    logging.captureWarnings(True)
    _configured = True
