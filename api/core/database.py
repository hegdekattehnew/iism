from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from api.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for every model in every module."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazily built so configuration is read at call time, not import time.

    Binding `settings` at import would make the engine unoverridable, which
    breaks tests and any runtime reconfiguration.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        # Explicit, not SQLAlchemy's silent 5+10 with a 30-second wait: a pool
        # sized by nobody is a pool nobody can reason about under load, and a
        # request that waits half a minute for a connection has already failed.
        server_settings = (
            {"statement_timeout": str(settings.db_statement_timeout_ms)}
            if settings.db_statement_timeout_ms > 0
            else {}
        )
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.db_echo,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout_seconds,
            connect_args={"server_settings": server_settings},
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)
    return _sessionmaker


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. One session per request, rolled back on error."""
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def one_of(column: str, values: tuple[str, ...], *, nullable: bool = False) -> str:
    """The SQL body of a CHECK, generated from the tuple that defines the values.

    These lists were spelled twice — once as a module constant and once as a
    string literal inside the `CheckConstraint` beside it — and the constants
    were then read by nothing at all. That is not merely redundant: `personal`
    was once added to `tenant_type` in the database by hand while the model's
    copy lagged, and **Alembic does not diff CHECK bodies**, so nothing flagged
    it. One list, used by both, removes the class of drift.

    The generated text matches the existing constraint bodies exactly, so no
    migration is required.
    """
    listed = ", ".join(f"'{v}'" for v in values)
    clause = f"{column} IN ({listed})"
    return f"{column} IS NULL OR {clause}" if nullable else clause
