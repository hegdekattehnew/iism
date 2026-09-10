"""Per-request correlation context, and the access log.

**Pure ASGI, not `BaseHTTPMiddleware`, and that is not a style preference.**
`BaseHTTPMiddleware` runs the downstream app with `task_group.start_soon`;
anyio *copies* the current context into the child task, and the child's
mutations do not propagate back to the parent. `user_id` and `tenant_id` are
resolved inside FastAPI dependencies -- `get_current_user`,
`authorization._context_for` -- which run downstream. Under
`BaseHTTPMiddleware` those bindings would be invisible by the time the access
line is written, and **every access line would be anonymous**. Raw ASGI keeps
the whole request in one task and one context, which is the entire point.

It replaces uvicorn's access log, which said

    INFO:  127.0.0.1:52509 - "GET /health/deep HTTP/1.1" 200 OK

and carried no duration, no request id, no user, no tenant -- and the
interpolated path, which puts a customer's slug in every log line.
"""

import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = structlog.get_logger("iism.http")

_MAX_ID_LEN = 64
# Everything an id may contain besides alphanumerics. Kept as a translation
# table so the check below is one pass and allocates nothing per request.
_STRIPPED = str.maketrans("", "", "-_")


def _incoming_request_id(scope: Scope) -> str | None:
    """An `X-Request-Id` from the caller, if it is safe to echo.

    An AWS ALB stamps `X-Amzn-Trace-Id`, not `X-Request-Id`, and it does not
    sanitise headers it does not own -- so this value is attacker-controlled.
    Accepting it verbatim would let a client write arbitrary text, including
    forged JSON, into every log line of their own request. Length-capped and
    restricted to an identifier alphabet, or discarded and replaced.
    """
    for name, value in scope["headers"]:
        if name == b"x-request-id":
            candidate = value.decode("latin-1").strip()
            if 0 < len(candidate) <= _MAX_ID_LEN and candidate.translate(_STRIPPED).isalnum():
                return candidate
            return None
    return None


def route_template(scope: Scope) -> str:
    """The *registered* path, never the interpolated one.

    `/org/acme-clinic/jobs/nurse-icu/publish` names a customer in every log
    line and gives CloudWatch a new field value per request; the template is
    one bounded dimension.

    FastAPI's `APIRoute.matches` puts itself in the scope, so `scope["route"]`
    is the template -- but only once the router has run, which is why every
    caller of this sits *below* `await self.app(...)`. Starlette's plain
    `Route`/`Mount` do not set it and an unmatched path sets nothing, so both
    fall back to a constant rather than to `scope["path"]`: a 404 flood must
    not become a cardinality flood.
    """
    path = getattr(scope.get("route"), "path", None)
    return path if isinstance(path, str) else "unmatched"


class RequestContextMiddleware:
    """Binds `request_id`, writes `http.request`, and owns the 500 log."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # On entry, not on exit. uvicorn gives each request a fresh task whose
        # context is copied from the server's, but the `ASGITransport` used in
        # tests does not -- there, one context serves every request in a test,
        # and a `user_id` from the previous request would leak onto this one's
        # access line. Clearing here is what makes both true.
        structlog.contextvars.clear_contextvars()
        request_id = _incoming_request_id(scope) or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                # Echoed so a bug report can quote it. `expose_headers` on the
                # CORS middleware is what lets the browser client read it.
                MutableHeaders(scope=message).append("x-request-id", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Starlette's `ServerErrorMiddleware` sits *above* this and always
            # re-raises after building its 500, so without this the traceback
            # reaches uvicorn unstructured and unjoinable to the request that
            # caused it. Logged here, where the context is still bound.
            log.exception(
                "http.request_failed",
                method=scope["method"],
                route=route_template(scope),
            )
            raise
        finally:
            # Deliberately no `clear_contextvars()` here: on the exception path
            # the error keeps travelling up to uvicorn, whose own
            # `uvicorn.error` record should carry the same `request_id`. The
            # next request clears on entry.
            log.info(
                "http.request",
                method=scope["method"],
                route=route_template(scope),
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
