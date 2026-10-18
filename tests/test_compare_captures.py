"""The per-family before-and-after table (Sprint 78, BL-19.9)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from compare_captures import FAMILIES, load, render, summarise  # noqa: E402


def _row(
    id_: str,
    screens: float,
    small: int,
    *,
    tiny: int = 0,
    svgs: int = 0,
    variant: str = "light",
    locale: str = "en",
) -> dict:
    return {
        "id": id_, "variant": variant, "locale": locale, "screens": screens,
        "smallTargets": small, "textUnder12px": tiny, "svgs": svgs, "errors": [],
    }  # fmt: skip


def test_the_runs_are_folded_into_one_row_per_family() -> None:
    before = [_row("jobs", 7.5, 4, svgs=2), _row("courses", 8.8, 1), _row("signin", 1.6, 3)]
    after = [_row("jobs", 7.9, 2, svgs=10), _row("courses", 9.0, 1), _row("signin", 1.7, 0)]
    table, only = summarise(before, after)
    assert only == []
    discovery = next(r for r in table if r["family"] == "home and discovery")
    assert (
        discovery["captures"],
        discovery["smallTargets_before"],
        discovery["smallTargets_after"],
    ) == (2, 5, 3)
    assert (discovery["svgs_before"], discovery["svgs_after"]) == (2, 10)
    assert discovery["screens_before"] == 16.3
    assert (
        next(r for r in table if r["family"] == "sign-in, sign-up and profile")[
            "smallTargets_after"
        ]
        == 0
    )


def test_a_capture_in_only_one_run_is_named_and_not_compared() -> None:
    table, only = summarise(
        [_row("jobs", 7, 1), _row("about", 3, 0)], [_row("jobs", 7, 1), _row("home", 6, 0)]
    )
    assert only == ["about.light.en", "home.light.en"]
    assert [r["family"] for r in table] == ["home and discovery"]
    assert "in only one run" in render(table, only)


def test_a_variant_is_a_different_capture() -> None:
    table, _ = summarise(
        [_row("jobs", 7, 1), _row("jobs", 7, 2, variant="dark")],
        [_row("jobs", 7, 1), _row("jobs", 7, 0, variant="dark")],
    )
    assert table[0]["captures"] == 2 and table[0]["smallTargets_after"] == 1


def test_an_id_with_no_family_is_shown_not_dropped() -> None:
    table, _ = summarise([_row("brand-new-page", 2, 1)], [_row("brand-new-page", 2, 0)])
    assert table[0]["family"] == "(unclassified)"


def test_a_run_with_nothing_in_it_is_a_failure_not_an_empty_table(tmp_path: Path) -> None:
    empty = tmp_path / "m.json"
    empty.write_text(json.dumps({"results": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load(empty)


def test_every_captured_page_has_a_family() -> None:
    measured = json.loads(
        (ROOT / "docs/design/screens/measurements.sprint77.json").read_text(encoding="utf-8")
    )
    ids = {r["id"] for r in measured["results"]}
    assert ids, "the check found no captures"
    assert ids <= set(FAMILIES), f"no family for: {sorted(ids - set(FAMILIES))}"
