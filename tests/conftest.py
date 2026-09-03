"""Test fixtures.

Real Postgres and Redis in disposable containers, so tests never share state
with the developer's running stack and behave identically in CI. Each test runs
inside a transaction that is rolled back, so no test can leak rows into another.
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def _containers() -> Iterator[tuple[str, str]]:
    with (
        PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg") as pg,
        RedisContainer("redis:7-alpine") as redis,
    ):
        db_url = pg.get_connection_url()
        redis_url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
        yield db_url, redis_url


@pytest.fixture(scope="session", autouse=True)
def _environment(_containers: tuple[str, str]) -> Iterator[None]:
    """Point settings at the containers before anything imports them."""
    db_url, redis_url = _containers
    os.environ["DATABASE_URL"] = db_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["ENVIRONMENT"] = "test"
    # A real-length key: PyJWT warns below 32 bytes for HMAC-SHA256, and the
    # warning is worth keeping meaningful rather than muting.
    os.environ["JWT_SECRET_KEY"] = "test-only-key-" + "x" * 40

    from api.core.config import get_settings

    # Settings are read lazily everywhere, so clearing the cache is enough to
    # repoint the engine and Redis client at the containers.
    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(ROOT / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    yield


@pytest.fixture
async def db() -> AsyncIterator:
    """A session wrapped in a transaction that is always rolled back."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from api.core.database import get_engine

    connection = await get_engine().connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def client(db) -> AsyncIterator:
    """HTTP client with the request-scoped session replaced by the rolled-back one."""
    from httpx import ASGITransport, AsyncClient

    from api.core.database import get_db_session
    from api.main import app

    async def _override() -> AsyncIterator:
        yield db

    app.dependency_overrides[get_db_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
