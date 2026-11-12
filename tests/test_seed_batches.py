"""The demonstration seed for batches (Sprint 103).

It writes through the product's own services, so what it makes obeys the invariants a real batch
does; what a test can hold without a populated database is that it refuses the two databases
whose contents a harness owns, and that it never touches the five candidates the golden set is
asserted on.
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "seed_batches.py"


def _load():
    spec = importlib.util.spec_from_file_location("seed_batches", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["iism_scale", "iism_e2e"])
def test_it_refuses_the_databases_a_harness_owns(monkeypatch, name):
    seed = _load()
    monkeypatch.setattr(
        seed,
        "get_settings",
        lambda: SimpleNamespace(database_url=f"postgresql+asyncpg://u@h/{name}"),
    )
    with pytest.raises(SystemExit) as stopped:
        seed._guard()
    assert name in str(stopped.value)


def test_it_allows_the_development_database(monkeypatch):
    seed = _load()
    monkeypatch.setattr(
        seed, "get_settings", lambda: SimpleNamespace(database_url="postgresql+asyncpg://u@h/iism")
    )
    seed._guard()


def test_the_golden_candidates_are_never_learners():
    seed = _load()
    golden = {f"+9190000000{n:02d}" for n in range(1, 6)}
    assert seed.LEARNER_PHONES, "the list it loops over must not be empty"
    assert golden.isdisjoint(seed.LEARNER_PHONES), "make evaluate asserts on these five"


def test_the_demonstration_covers_the_four_situations():
    seed = _load()
    (_, _, academy_sells, academy_delivers) = seed.ACADEMY
    (_, _, partner_sells, partner_delivers) = seed.PARTNER
    assert (academy_sells, academy_delivers) == (True, True), "sells and delivers its own"
    assert (partner_sells, partner_delivers) == (False, True), "delivers only"
    assert len(seed.ACADEMY_CENTRES) >= 2 and len(seed.PARTNER_CENTRES) >= 3
