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
from api.modules.skills import router as skills_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await close_task_pool()
    await close_redis()
    await dispose_engine()


_settings = get_settings()

app = FastAPI(
    title=_settings.app_name,
    version=_settings.app_version,
    lifespan=lifespan,
)

# The web client is a separate origin in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.web_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
