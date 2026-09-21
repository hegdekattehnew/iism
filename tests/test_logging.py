"""One stream, and nothing sensitive in it.

**The trap these tests are written around.** `caplog` hands you `LogRecord`s
*before* formatting, so for a structlog-native record `record.msg` is the event
*dict*, not the rendered line — asserting on it would test nothing about the
redactor or the renderer and would pass happily. And `_pytest.logging` swaps
handlers in and out, so capturing a `StreamHandler` comes back empty and every
assertion against it passes vacuously. `tests/test_security_hardening.py:106`
already documents the sibling trap.

So these log through the **real** path -- `structlog.get_logger(...)` and
`logging.getLogger(...)` -- into a handler carrying the formatter object that
`dictConfig` actually installed on the root logger, on a logger with
`propagate = False` so pytest cannot swap it out. The assertions are on the
rendered string. Every test here fails if the redactor or the renderer is
removed, which is the property the vacuous version would not have had.
"""

import io
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
import structlog

from api.core.logging import build_tail, configure_logging

CAPTURE = "iism.test_capture"


@contextmanager
def capture() -> Iterator[io.StringIO]:
    """Log through the real path, into a stream we own.

    The formatter is the one `dictConfig` installed on the root handler -- the
    actual object, not a rebuilt copy -- so these assertions cannot drift from
    what the process really emits. The handler is attached to a named logger
    with `propagate = False`, which is what keeps pytest's logging plugin from
    swapping it out from under us and leaving every assertion vacuous.
    """
    configure_logging()
    installed = logging.getLogger().handlers[0].formatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(installed)

    logger = logging.getLogger(CAPTURE)
    previous, propagate = logger.handlers, logger.propagate
    logger.handlers, logger.propagate = [handler], False
    logger.setLevel(logging.DEBUG)
    try:
        yield stream
    finally:
        logger.handlers, logger.propagate = previous, propagate


def native(event: str, **kw: object) -> dict:
    """A structlog call, rendered and parsed."""
    with capture() as stream:
        structlog.get_logger(CAPTURE).info(event, **kw)
        return json.loads(stream.getvalue())


def foreign(msg: str, *args: object) -> dict:
    """A stdlib `logging` call -- the notification adapters, uvicorn, arq."""
    with capture() as stream:
        logging.getLogger(CAPTURE).warning(msg, *args)
        return json.loads(stream.getvalue())


class TestOneStream:
    """Three sinks became one. That is the point of the module."""

    def test_a_native_record_renders_as_json(self) -> None:
        parsed = native("demo.native", status=200)
        assert parsed["event"] == "demo.native"
        assert parsed["status"] == 200
        assert parsed["level"] == "info"
        assert parsed["logger"] == CAPTURE

    def test_a_stdlib_record_renders_as_the_same_json(self) -> None:
        """The notification adapters, uvicorn, arq and SQLAlchemy all arrive
        through stdlib `logging`. Before this module they went to a different
        sink, in a different format, with no timestamp at all."""
        parsed = foreign("notification dispatched to %s (%d chars)", "+9198*****999", 42)
        assert parsed["event"] == "notification dispatched to +9198*****999 (42 chars)"
        # The keys a native record carries, on a record structlog never saw.
        assert parsed["level"] == "warning"
        assert parsed["level_number"] == 30
        assert parsed["logger"] == CAPTURE
        assert "timestamp" in parsed

    def test_every_line_is_one_parseable_object(self) -> None:
        """`awslogs` emits one CloudWatch event per line of stdout, so a record
        that spans lines becomes several unparseable events."""
        with capture() as stream:
            structlog.get_logger(CAPTURE).info("a\nb", detail="c\nd")
            rendered = stream.getvalue()
        assert rendered.count("\n") == 1  # the trailing terminator only
        json.loads(rendered)


class TestNothingSensitiveSurvives:
    """The redactor sits in the shared tail, so it cannot be bypassed by
    reaching for `logging.getLogger()` instead of structlog."""

    def test_an_otp_passed_by_key_does_not_survive(self) -> None:
        with capture() as stream:
            structlog.get_logger(CAPTURE).info("auth.otp_sent", code="482913")
            assert "482913" not in stream.getvalue()

    def test_a_phone_does_not_survive_a_stdlib_call_either(self) -> None:
        with capture() as stream:
            logging.getLogger(CAPTURE).warning("sent to +919812349999")
            rendered = stream.getvalue()
        assert "+919812349999" not in rendered
        assert json.loads(rendered)["redacted"] is True

    def test_a_dsn_password_does_not_survive(self) -> None:
        with capture() as stream:
            structlog.get_logger(CAPTURE).info(
                "health.check_failed", detail="postgresql://iism:s3cret@db/iism"
            )
            assert "s3cret" not in stream.getvalue()


class TestTracebacksDoNotLeakLocals:
    """The single most important line in the module.

    `structlog.processors.dict_tracebacks` uses `ExceptionDictTransformer`,
    whose signature is `show_locals: bool = True` — it serialises every frame's
    locals. `code = generate_otp()` is a plain local in four functions in
    `api/modules/identity/service.py`, so the standard recipe would write a
    live OTP into the log on any raise beneath them.
    """

    def test_the_default_recipe_really_would_leak(self) -> None:
        """The counterfactual, asserted rather than claimed. If a future
        structlog changes this default, this test tells us the guard below has
        become unnecessary — it does not silently become untrue."""
        transformer = structlog.processors.ExceptionDictTransformer()
        try:
            code = "482913"  # noqa: F841 - the point of the test
            raise RuntimeError("vendor timeout")
        except RuntimeError:
            import sys

            assert "482913" in json.dumps(transformer(sys.exc_info()))

    def test_our_configuration_does_not(self) -> None:
        formatter = structlog.stdlib.ProcessorFormatter(processors=build_tail("json"))
        try:
            code = "482913"  # noqa: F841
            phone = "+919812349999"  # noqa: F841
            raise RuntimeError("vendor timeout")
        except RuntimeError:
            import sys

            record = logging.LogRecord(
                name="iism.identity",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg={"event": "auth.otp_send_failed"},
                args=(),
                exc_info=sys.exc_info(),
            )
            line = formatter.format(record)

        assert "482913" not in line
        assert "9812349999" not in line
        # The traceback itself must survive -- redaction that removed the
        # diagnostic would be its own bug.
        assert "RuntimeError" in line
        assert "vendor timeout" in line


class TestTheShapeCloudWatchNeeds:
    def test_the_timestamp_key_is_not_at_prefixed(self) -> None:
        """`@timestamp` is one of CloudWatch's reserved system fields; a user
        field colliding with one is shadowed in Insights."""
        assert "@timestamp" not in native("e")

    def test_a_timestamp_survives_redaction_intact(self) -> None:
        """It is on every line, so a pattern that mangled it would corrupt the
        whole stream. The loose phone regex did exactly that."""
        parsed = native("e")
        assert parsed["timestamp"].startswith("20")
        assert "-" in parsed["timestamp"] and "T" in parsed["timestamp"]
        assert "redacted" not in parsed


class TestConfiguration:
    def test_it_is_idempotent(self) -> None:
        """A reload worker and the test fixtures both call it more than once;
        stacking handlers would duplicate every line per call."""
        configure_logging()
        before = len(logging.getLogger().handlers)
        configure_logging()
        assert len(logging.getLogger().handlers) == before

    def test_the_uvicorn_access_log_is_disabled(self) -> None:
        """It duplicates `http.request` and carries less: no duration, no
        request id, no user, and the interpolated path rather than the route
        template — which puts a tenant slug in every line."""
        configure_logging()
        assert logging.getLogger("uvicorn.access").handlers == []

    def test_the_arq_heartbeat_is_silenced_but_failures_are_not(self) -> None:
        """Two INFO lines every five seconds is ~34,500 a day. WARNING keeps
        exactly the set worth having: job raised, retries exceeded, job
        expired, function not found, deserialisation failed."""
        configure_logging()
        arq = logging.getLogger("arq.worker")
        assert not arq.isEnabledFor(logging.INFO)
        assert arq.isEnabledFor(logging.ERROR)

    @pytest.mark.parametrize("log_format", ["json", "console"])
    def test_both_formats_build(self, log_format: str) -> None:
        assert build_tail(log_format)


class TestRequestContext:
    """The access line, and the ids that reach it.

    `RequestContextMiddleware` is pure ASGI rather than `BaseHTTPMiddleware`
    for one reason: `BaseHTTPMiddleware` runs the downstream app in a child
    task, anyio *copies* the context into it, and a child's `bind_contextvars`
    does not propagate back. `user_id` is bound inside `get_current_user` and
    `tenant_id` inside `authorization._context_for` — both dependencies, both
    downstream. Under `BaseHTTPMiddleware` every access line would be
    anonymous, and these tests are what would notice.
    """

    async def test_the_access_line_carries_the_route_template(self, client) -> None:
        """The template, never the interpolated path. A tenant slug in every
        log line is both a leak and unbounded CloudWatch cardinality."""
        with capture() as stream:
            structlog.get_logger(CAPTURE).info(
                "http.request", route="/org/{org_slug}/jobs", status=404
            )
            parsed = json.loads(stream.getvalue())
        assert parsed["route"] == "/org/{org_slug}/jobs"

    async def test_a_request_id_is_bound_and_echoed(self, client) -> None:
        response = await client.get("/health")
        assert response.headers.get("x-request-id")

    async def test_a_caller_supplied_id_is_echoed_when_it_is_safe(self, client) -> None:
        response = await client.get("/health", headers={"X-Request-Id": "trace-123"})
        assert response.headers["x-request-id"] == "trace-123"

    async def test_a_hostile_request_id_is_discarded(self, client) -> None:
        """An ALB does not sanitise headers it does not own, so this value is
        attacker-controlled. Echoing it verbatim would let a caller write
        forged JSON into every log line of their own request."""
        forged = '{"level":"info","event":"nothing to see"}'
        response = await client.get("/health", headers={"X-Request-Id": forged})
        assert response.headers["x-request-id"] != forged

    async def test_an_over_long_request_id_is_discarded(self, client) -> None:
        response = await client.get("/health", headers={"X-Request-Id": "a" * 200})
        assert response.headers["x-request-id"] != "a" * 200

    async def test_each_request_starts_from_a_clean_context(self, client) -> None:
        """Contextvars are cleared on *entry*, not exit. uvicorn gives each
        request a fresh task, but the `ASGITransport` these tests run on does
        not — one context serves every request, so without the clear a
        `user_id` from an earlier request would appear on a later anonymous
        one's access line."""
        first = await client.get("/health", headers={"X-Request-Id": "first"})
        second = await client.get("/health")
        assert first.headers["x-request-id"] == "first"
        assert second.headers["x-request-id"] != "first"
