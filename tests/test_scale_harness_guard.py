"""The scale harness refuses to run anywhere but a database built for it (Sprint 49).

`scripts/seed_scale.py` deletes and rewrites synthetic rows to be idempotent, and "the
wrong `DATABASE_URL`" is how a harness becomes an incident. Both scripts therefore check
the database *name* before opening a connection -- so these tests need no database, and
the URL they pass points at a port nothing listens on: reaching a connection attempt would
itself be the failure.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UNREACHABLE = "postgresql+asyncpg://iism:iism@127.0.0.1:1/{name}"


def _run(script: str, database: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": UNREACHABLE.format(name=database)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize("script", ["seed_scale.py", "benchmark_matching.py"])
@pytest.mark.parametrize("database", ["iism", "iism_test", "iism_scale_backup", "scale"])
def test_it_refuses_a_database_that_is_not_a_scale_database(script: str, database: str) -> None:
    result = _run(script, database)

    assert result.returncode != 0
    assert "Refusing" in (result.stdout + result.stderr)
    # The refusal came from the name check, not from a failed connection.
    assert "Connect call failed" not in result.stderr


def test_a_scale_database_gets_past_the_guard() -> None:
    """The non-vacuity guard: a name ending `_scale` is *not* refused, so the tests above
    are about the name and not about the script refusing everything."""
    result = _run("seed_scale.py", "iism_scale")

    assert "Refusing" not in (result.stdout + result.stderr)
    # It got as far as trying to connect, and failed there.
    assert result.returncode != 0


def test_a_skew_below_one_is_refused() -> None:
    result = _run("seed_scale.py", "iism_scale", "--skew", "0.5")

    assert result.returncode != 0
    assert "--skew must be at least 1" in (result.stdout + result.stderr)
