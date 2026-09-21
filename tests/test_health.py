"""Sprint 1: the skeleton is wired together."""

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_liveness_does_not_touch_dependencies(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_deep_health_reports_every_component(client: AsyncClient) -> None:
    response = await client.get("/health/deep")
    assert response.status_code == 200
    body = response.json()
    assert {c["name"] for c in body["components"]} == {"postgres", "redis", "worker"}


async def test_postgres_and_redis_are_up(client: AsyncClient) -> None:
    body = (await client.get("/health/deep")).json()
    by_name = {c["name"]: c for c in body["components"]}
    assert by_name["postgres"]["status"] == "up"
    assert by_name["redis"]["status"] == "up"


async def test_pgvector_extension_is_enabled(db: AsyncSession) -> None:
    """Migration 0001 must enable pgvector; every later embedding column needs it."""
    version = await db.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
    assert version is not None


async def test_worker_reported_down_when_no_heartbeat(client: AsyncClient) -> None:
    """No worker runs in the test environment, so this must fail closed."""
    body = (await client.get("/health/deep")).json()
    worker = next(c for c in body["components"] if c["name"] == "worker")
    assert worker["status"] == "down"
    assert body["status"] == "down"
