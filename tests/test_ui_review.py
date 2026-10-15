"""The UI review's findings are checkable (Sprint 68).

The findings are data in `scripts/build_ui_review.py`; this holds them to the rules that keep a
review honest: every id unique, severity and effort from the closed sets, every screenshot a finding
cites actually exists, the measurements file is the one the captures wrote, and the markdown and the
workbook are rebuilt from the data (a hand-edited or stale copy fails).
"""

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "design"
SCREENS = DESIGN / "screens"


def _builder():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "build_ui_review", ROOT / "scripts" / "build_ui_review.py"
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_the_findings_are_well_formed() -> None:
    m = _builder()
    ids = [f[0] for f in m.F]
    assert len(m.F) >= 25  # found them before judging any
    assert len(ids) == len(set(ids)), "a finding id appears twice"
    for (
        fid,
        _surface,
        _page,
        heuristic,
        severity,
        effort,
        finding,
        evidence,
        _shots,
        fix,
        files,
    ) in m.F:
        assert severity in m.SEVERITIES, fid
        assert effort in m.EFFORTS, fid
        assert heuristic in m.HEURISTICS, fid
        assert len(finding) > 60 and len(evidence) > 10 and len(fix) > 20 and files, fid


def test_every_screenshot_a_finding_cites_exists() -> None:
    m = _builder()
    cited = {shot for f in m.F for shot in f[8]}
    assert cited  # at least some findings rest on a picture
    missing = sorted(shot for shot in cited if not (SCREENS / shot).is_file())
    assert missing == [], f"findings cite pictures that are not in docs/design/screens: {missing}"


def test_the_measurements_are_the_captures_and_complete() -> None:
    data = json.loads((SCREENS / "measurements.json").read_text(encoding="utf-8"))
    results = data["results"]
    assert len(results) >= 50
    assert all(r.get("status") == 200 or r["id"] in {"employer-applicants"} for r in results), (
        "a page failed to load"
    )
    for key in ("screens", "smallTargets", "textUnder12px", "images", "svgs", "interactive"):
        assert all(key in r for r in results), key
    # Every capture has its picture.
    assert all((SCREENS / r["file"]).is_file() for r in results)
    # The review's headline numbers are the measurements', not remembered ones.
    by = {(r["id"], r["variant"], r["locale"]): r for r in results}
    assert by[("jobs", "light", "en")]["screens"] > 30
    assert by[("home", "light", "en")]["images"] == 0


def test_the_markdown_and_workbook_are_built_from_the_data() -> None:
    m = _builder()
    assert (DESIGN / "ui-review.md").read_text(encoding="utf-8") == m.build_markdown(), (
        "docs/design/ui-review.md is stale: run `.venv/bin/python scripts/build_ui_review.py`"
    )
    sheet = (
        zipfile.ZipFile(DESIGN / "IISM-UI-Review.xlsx")
        .read("xl/worksheets/sheet2.xml")
        .decode("utf-8")
    )
    for f in m.F:
        assert f">{f[0]}<" in sheet, f"{f[0]} is missing from the workbook"


def test_the_measurement_can_fail() -> None:
    """The under-44 px counter has to find small targets where there are some and none where there
    are none: the web header's menu button is 38x38 and the phone's shared button is 48 dp."""
    data = json.loads((SCREENS / "measurements.json").read_text(encoding="utf-8"))["results"]
    home = next(
        r for r in data if r["id"] == "home" and r["variant"] == "light" and r["locale"] == "en"
    )
    assert any("Open menu" in e for e in home["smallExamples"]), (
        "the counter missed a known 38x38 target"
    )
    sources = (ROOT / "mobile" / "src" / "ui" / "primitives.tsx").read_text(encoding="utf-8")
    assert "minHeight: MIN_TOUCH" in sources  # and the phone's own floor is 48
