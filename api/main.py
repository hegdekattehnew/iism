import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from arq.jobs import Job, JobStatus
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.core.cache import close_redis
from api.core.config import get_settings
from api.core.database import dispose_engine
from api.core.health import DeepHealth, check_database, check_redis, check_worker
from api.core.logging import configure_logging
from api.core.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from api.core.tasks import close_task_pool, get_task_pool
from api.modules.analytics import router as analytics_router
from api.modules.geography import router as geography_router
from api.modules.identity import account_router, organisation_router
from api.modules.identity import router as auth_router
from api.modules.marketplace import (
    course_publishing_router,
    courses_router,
    jobs_router,
    marketplace_router,
    profile_router,
    publishing_router,
)
from api.modules.matching import employer_org_router, mount_employer_console
from api.modules.matching import router as matching_router
from api.modules.privacy import router as privacy_router
from api.modules.skills import router as skills_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Again, deliberately. uvicorn runs its own `dictConfig` *after* importing
    # this module, which re-attaches its text handlers to the `uvicorn.*`
    # loggers and undoes the call below. Lifespan startup is the first hook
    # that runs after uvicorn has finished, and `configure_logging` is
    # idempotent, so this is a correction rather than a second configuration.
    configure_logging()
    yield
    await close_task_pool()
    await close_redis()
    await dispose_engine()


# The one place a module-level `get_settings()` is correct, and it needs saying
# because the convention forbids it outright.
#
# The rule exists because a frozen `settings` is unoverridable, which silently
# points the engine at the wrong database in tests. Neither half applies here.
# The app *object* is assembled once per process and cannot be built without a
# title, an allowed origin and an environment; and the two decisions taken from
# this value -- whether the demo task router and the unauthenticated employer
# console mount -- are exercised by `tests/test_security_hardening.py`, which
# boots a fresh subprocess per ENVIRONMENT and reads the resulting route table.
# A guard on the app's own assembly is tested by assembling the app, not by
# overriding a dependency.
#
# Everything downstream of assembly -- handlers, services, the engine -- calls
# `get_settings()` at call time. The two handlers below are the pattern.
_settings = get_settings()

# Before the app object, so anything the routers log at import time is already
# formatted and redacted rather than going out through structlog's defaults.
configure_logging()

app = FastAPI(
    title=_settings.app_name,
    version=_settings.app_version,
    lifespan=lifespan,
    # Interactive docs are a map of every route, parameter and schema, handed to
    # whoever asks. Useful on a laptop -- `make gen-api` reads `/openapi.json` --
    # and a reconnaissance gift anywhere else. Same allowlist as the demo routes.
    docs_url="/docs" if _settings.is_local else None,
    redoc_url="/redoc" if _settings.is_local else None,
    openapi_url="/openapi.json" if _settings.is_local else None,
)

# `add_middleware` prepends, so these read inside-out. The resulting order,
# outermost first:
#
#   RequestContext  -- every response, rejections included, gets an access line
#                      and an x-request-id
#   SecurityHeaders -- and every response, rejections included, gets the headers
#   CORS            -- outside the two below, so a 413 or 429 still carries CORS
#                      headers and the browser can read the status instead of
#                      reporting an opaque network error
#   BodySizeLimit
#   RateLimit
app.add_middleware(RateLimitMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.web_base_url],
    # False: authentication is a bearer header, and no route sets or reads a
    # cookie. Allowing credentials across origins was a permission granted for
    # nothing.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # So the browser client can read the id and a bug report can quote it.
    expose_headers=["x-request-id"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

app.include_router(skills_router)
app.include_router(geography_router)
app.include_router(jobs_router)
app.include_router(courses_router)
app.include_router(marketplace_router)
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(organisation_router)
app.include_router(profile_router)
app.include_router(publishing_router)
app.include_router(course_publishing_router)
app.include_router(matching_router)
app.include_router(analytics_router)
app.include_router(privacy_router)

app.include_router(employer_org_router)

# The *demonstration* console is unauthenticated, so it mounts in local
# environments only. The authenticated one above needs no guard. The flag is
# reported by /health, so which surfaces are live is answerable without reading
# this file.
employer_demo_enabled = mount_employer_console(app)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str | bool]:
    """Liveness only. Never touches a dependency, so it cannot cascade."""
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": settings.app_version,
        # Whether the unauthenticated demonstration console is mounted. Worth
        # answering over HTTP rather than by reading source: it is the one
        # surface whose presence is a security question.
        "employer_demo": employer_demo_enabled,
    }


@app.get("/health/deep", response_model=DeepHealth, tags=["health"])
async def health_deep() -> DeepHealth:
    """Readiness. Probes each dependency independently and in parallel."""
    settings = get_settings()
    components = await asyncio.gather(check_database(), check_redis(), check_worker())
    overall = "up" if all(c.status == "up" for c in components) else "down"
    return DeepHealth(
        status=overall,
        environment=settings.environment,
        version=settings.app_version,
        components=list(components),
    )


# ------------------------------------------------------------------ demo task
# Sprint 1 verification for the homepage dev panel. Registered ONLY in local
# environments: unauthenticated and it enqueues work, so in production it would
# be an open queue-flooding vector. The dev panel is not part of the product
# surface, so removing it outside development costs nothing.


tasks_router = APIRouter()


class TaskEnqueued(BaseModel):
    job_id: str


class TaskStatus(BaseModel):
    job_id: str
    status: str
    result: dict[str, Any] | None = None


@tasks_router.post("/tasks/ping", response_model=TaskEnqueued, tags=["tasks"])
async def enqueue_ping(note: str = "") -> TaskEnqueued:
    pool = await get_task_pool()
    job = await pool.enqueue_job("ping", note)
    if job is None:  # pragma: no cover - only on a duplicate job id
        raise RuntimeError("could not enqueue job")
    return TaskEnqueued(job_id=job.job_id)


@tasks_router.get("/tasks/{job_id}", response_model=TaskStatus, tags=["tasks"])
async def task_status(job_id: str) -> TaskStatus:
    pool = await get_task_pool()
    job = Job(job_id, pool)
    status = await job.status()
    result: dict[str, Any] | None = None
    if status is JobStatus.complete:
        try:
            result = await job.result(timeout=1)
        except Exception:
            result = None
    return TaskStatus(job_id=job_id, status=status.value, result=result)


# Only mounted locally; in any other environment these paths do not exist.
if _settings.is_local:
    app.include_router(tasks_router)
