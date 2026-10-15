"""The mobile size ceiling (Sprint 66, ADR-077). A budget that cannot fail is not one."""

import json
from pathlib import Path

import pytest

from scripts.check_mobile_budget import BUDGET, measure, over_budget


def _export(tmp_path: Path, size: int) -> Path:
    bundle = tmp_path / "_expo" / "static" / "js" / "android"
    bundle.mkdir(parents=True)
    (bundle / "entry-abc.hbc").write_bytes(b"x" * size)
    return tmp_path


def test_the_committed_budget_is_read_and_has_both_ceilings() -> None:
    ceilings = json.loads(BUDGET.read_text(encoding="utf-8"))
    assert {"android_bundle_bytes", "assets_bytes"} <= set(ceilings)
    assert all(ceilings[k] > 100_000 for k in ("android_bundle_bytes", "assets_bytes"))


def test_a_measurement_inside_the_ceiling_passes_and_one_over_it_names_both_numbers() -> None:
    ceilings = {"android_bundle_bytes": 1000, "assets_bytes": 500}
    assert over_budget({"android_bundle_bytes": 1000, "assets_bytes": 500}, ceilings) == []
    [problem] = over_budget({"android_bundle_bytes": 1001, "assets_bytes": 500}, ceilings)
    assert "1,001" in problem and "1,000" in problem


def test_a_ceiling_with_no_measurement_and_a_measurement_with_no_ceiling_are_defects() -> None:
    assert over_budget({}, {"assets_bytes": 5})
    assert over_budget({"assets_bytes": 5}, {})


def test_it_measures_the_hermes_bundle_and_the_assets(tmp_path: Path) -> None:
    export = _export(tmp_path / "export", 2048)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "a.png").write_bytes(b"y" * 100)
    (assets / "b.png").write_bytes(b"y" * 50)
    assert measure(export, assets) == {"android_bundle_bytes": 2048, "assets_bytes": 150}


def test_a_missing_bundle_or_missing_assets_is_an_error_not_a_pass(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "a.png").write_bytes(b"y")
    with pytest.raises(FileNotFoundError):
        measure(tmp_path / "empty-export", assets)
    with pytest.raises(FileNotFoundError):
        measure(_export(tmp_path / "export", 10), tmp_path / "no-assets")
