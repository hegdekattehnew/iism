"""What every connection is told when it opens (Sprint 50).

The suite's own engine is built by `get_engine()` from the same settings production uses, so
what the server reports for a session here is what a request would get.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import Settings


async def test_jit_is_off_for_every_connection(db: AsyncSession) -> None:
    """Postgres compiles a query whose estimated cost passes 100,000, which cost ~600 ms per
    chunk on the batched programme report and bought nothing (Sprint 50)."""
    assert await db.scalar(text("SHOW jit")) == "off"


def test_it_can_be_put_back() -> None:
    assert Settings().db_jit is False
    assert Settings(db_jit=True).db_jit is True


@pytest.mark.parametrize("flag,expected", [(False, "off"), (True, "on")])
async def test_the_setting_is_what_reaches_the_engine(
    flag: bool, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.core import database
    from api.core.config import get_settings

    monkeypatch.setenv("DB_JIT", "true" if flag else "false")
    get_settings.cache_clear()
    monkeypatch.setattr(database, "_engine", None)
    try:
        engine = database.get_engine()
        async with engine.connect() as connection:
            assert await connection.scalar(text("SHOW jit")) == expected
        await engine.dispose()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        database._engine = None
