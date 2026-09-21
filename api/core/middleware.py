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

import json
import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.core.config import get_settings

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


# --------------------------------------------------------------------------
# Hardening. Three more pure-ASGI layers, for the same reason as the one above:
# `BaseHTTPMiddleware` runs the app in a child task, and these must see the
# real request and the real response.


async def _reject(
    send: Send, status: int, detail: str, headers: list[tuple[bytes, bytes]] | None = None
) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *(headers or []),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


# Responses that carry a person's data. The same list the service worker's DENY
# list guards one layer up: nothing personal may sit in a shared cache.
_PRIVATE_PREFIXES = ("/auth/", "/me", "/org/")
# Swagger UI loads its own scripts and styles; a `default-src 'none'` policy
# would blank it. It is mounted in local environments only.
_DOCS_PREFIXES = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware:
    """The response headers a browser needs to be told.

    None were set anywhere, while the web client keeps its tokens in
    localStorage -- readable by any script on the page, so everything that keeps
    foreign script and framing out matters more, not less.

    This is the API's half; the web app sets its own in `next.config.ts`. An API
    returns JSON and never needs to load anything, so its policy can be the
    strictest there is.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]
        hsts = not get_settings().is_local

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("x-content-type-options", "nosniff")
                headers.setdefault("x-frame-options", "DENY")
                headers.setdefault("referrer-policy", "no-referrer")
                headers.setdefault("permissions-policy", "camera=(), microphone=(), geolocation=()")
                if not path.startswith(_DOCS_PREFIXES):
                    headers.setdefault(
                        "content-security-policy", "default-src 'none'; frame-ancestors 'none'"
                    )
                if path.startswith(_PRIVATE_PREFIXES):
                    headers["cache-control"] = "no-store"
                # Over plain HTTP in development a browser ignores it anyway;
                # outside development it must never be missing.
                if hsts:
                    headers.setdefault(
                        "strict-transport-security", "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Refuse a request body larger than `max_request_body_bytes`.

    Declared length is checked before a byte is read, so an honest client gets
    a clean 413. A body with no declared length is counted as it arrives and
    abandoned once it passes the cap; FastAPI reports an unreadable body as a
    400, which is the right family of answer and still never buffers the rest.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = get_settings().max_request_body_bytes
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > limit:
                    log.warning("http.body_too_large", declared=declared, limit=limit)
                    await _reject(send, 413, "Request body too large")
                    return

        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await _reject(send, 413, "Request body too large")


def _limiter_identity(scope: Scope) -> str:
    """Who a request counts against: the signed-in user, else the client IP.

    Per user when there is a valid access token, because Indian mobile carriers
    put many subscribers behind one address and a per-IP limit would throttle
    strangers for each other. The token is only *decoded* here -- no database
    read -- and an invalid one falls back to the IP rather than erroring, since
    rejecting it is the route's job, not the limiter's.
    """
    from api.core.security import decode_token  # local: security imports the DB layer

    settings = get_settings()
    for name, value in scope["headers"]:
        if name == b"authorization":
            token = value.decode("latin-1").removeprefix("Bearer ").strip()
            try:
                return "u:" + str(decode_token(token, "access")["sub"])
            except Exception:  # noqa: BLE001 - any invalid token counts as anonymous
                break

    client = scope.get("client")
    ip = client[0] if client else "unknown"
    if settings.rate_limit_trust_forwarded:
        for name, value in scope["headers"]:
            if name == b"x-forwarded-for":
                ip = value.decode("latin-1").split(",")[0].strip()
                break
    return "ip:" + ip


class RateLimitMiddleware:
    """A fixed one-minute window per identity, per class of request.

    Only the OTP flow was limited; `/auth/refresh`, search and every write were
    open. A middleware rather than a dependency on each route, for the reason
    `require()` absorbed `require_publisher_of` in Sprint 15: **a guard each
    handler must remember is one that eventually is not there.**

    Three classes -- sign-in attempts, writes, reads -- because they cost
    different things. `GET /auth/me` is a read: the client calls it on every
    page, and lumping it in with sign-in attempts would throttle navigation.

    Fails **open**. If Redis is unreachable the request proceeds and the outage
    is logged: an unavailable limiter must not become an unavailable platform.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] == "OPTIONS"
            or scope["path"].startswith("/health")
        ):
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        if not settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        method: str = scope["method"]
        path: str = scope["path"]
        if path.startswith("/auth/") and method == "POST":
            bucket, limit = "auth", settings.rate_limit_auth_per_minute
        elif method in ("POST", "PUT", "PATCH", "DELETE"):
            bucket, limit = "write", settings.rate_limit_writes_per_minute
        else:
            bucket, limit = "read", settings.rate_limit_reads_per_minute

        # The identity is in the key and never in the log line: an IP address
        # is personal data, and the key expires in seventy seconds anyway.
        key = f"ratelimit:{bucket}:{_limiter_identity(scope)}:{int(time.time() // 60)}"
        try:
            from api.core.cache import get_redis  # local: keeps this module DB-free

            redis = get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 70)
        except Exception:  # noqa: BLE001 - fail open, by design
            log.warning("http.rate_limit_unavailable", bucket=bucket)
            await self.app(scope, receive, send)
            return

        if count > limit:
            log.warning("http.rate_limited", bucket=bucket, limit=limit)
            await _reject(
                send,
                429,
                "Too many requests. Please wait a minute and try again.",
                headers=[(b"retry-after", b"60")],
            )
            return
        await self.app(scope, receive, send)
