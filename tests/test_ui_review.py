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


def test_every_finding_marked_fixed_is_a_finding_and_says_what_was_done() -> None:
    """Sprints 69 and 70 closed fourteen findings; the review says which, and how far each went."""
    m = _builder()
    ids = {f[0] for f in m.F}
    assert m.FIXED, "no finding is marked fixed"
    assert set(m.FIXED) <= ids, f"marked fixed but not a finding: {sorted(set(m.FIXED) - ids)}"
    for fid, what in m.FIXED.items():
        assert what.startswith(("Fixed in Sprint 69", "Fixed in Sprint 70")), fid
        assert len(what) > 60, fid  # says what was done, not just that something was
    # And the markdown shows it: the status column is not dropped on the way to the reader.
    markdown = (DESIGN / "ui-review.md").read_text(encoding="utf-8")
    for fid in m.FIXED:
        row = next(line for line in markdown.splitlines() if line.startswith(f"| **{fid}**"))
        assert "Fixed in Sprint 6" in row or "Fixed in Sprint 7" in row, fid
    open_row = next(line for line in markdown.splitlines() if line.startswith("| **UI-03**"))
    assert open_row.rstrip().endswith("| Open |")


def test_the_sprint_69_remeasurement_is_the_same_captures_and_shows_the_fix() -> None:
    """The 'after' numbers come from the same script over the same pages, and the claims the review
    makes about them are the file's, not remembered ones (Sprint 69)."""
    before = {
        (r["id"], r["variant"], r["locale"]): r
        for r in json.loads((SCREENS / "measurements.json").read_text(encoding="utf-8"))["results"]
    }
    after = {
        (r["id"], r["variant"], r["locale"]): r
        for r in json.loads((SCREENS / "measurements.sprint69.json").read_text(encoding="utf-8"))[
            "results"
        ]
    }
    assert len(after) == len(before) >= 50 and set(after) == set(before), "not the same captures"
    assert all(r.get("status") == 200 or r["id"] in {"employer-applicants"} for r in after.values())
    key = ("jobs", "light", "en")
    # The list that used to draw 148 cards in 42 screens pages now.
    assert before[key]["screens"] > 30 and after[key]["screens"] < 10
    # Nothing under 12 px anywhere (was hundreds on the lists).
    assert sum(r["textUnder12px"] for r in before.values()) > 1000
    assert all(r["textUnder12px"] == 0 for r in after.values())
    # The header and footer no longer add targets under 44 px on any page: what is left is
    # in the page's own content (inline links, a few buttons), which the review still counts.
    chrome = {
        "Open menu", "IISM", "Jobs", "Courses", "Skills", "How it works", "About", "Contact",
        "Careers", "Privacy policy", "Terms of use", "Grievance redressal", "For employers",
        "For providers",
    }  # fmt: skip
    for k, r in after.items():
        labels = {e.split(" ", 2)[2].strip() for e in r["smallExamples"] if e.count(" ") >= 2}
        assert not (labels & chrome), (k, r["smallExamples"])
    # ...and that the same test finds them in the baseline, or it proves nothing.
    assert any(
        {e.split(" ", 2)[2].strip() for e in r["smallExamples"] if e.count(" ") >= 2} & chrome
        for r in before.values()
    )
    assert after[key]["smallTargets"] == 0 < before[key]["smallTargets"]
    for pictured in (
        "sprint69.jobs.light.en.jpg",
        "sprint69.jobs.hi.hi.jpg",
        "sprint69.job-detail.light.en.jpg",
        "sprint69.job-detail.hi.hi.jpg",
    ):
        assert (SCREENS / pictured).is_file(), pictured


def test_the_sprint_70_remeasurement_is_the_same_captures_and_shows_the_fix() -> None:
    """The homepage lost its framework band and its audience cards, the matches page opens on the
    matches (Sprint 70), and the numbers the review quotes for it are the file's."""
    before = {
        (r["id"], r["variant"], r["locale"]): r
        for r in json.loads((SCREENS / "measurements.json").read_text(encoding="utf-8"))["results"]
    }
    after = {
        (r["id"], r["variant"], r["locale"]): r
        for r in json.loads((SCREENS / "measurements.sprint70.json").read_text(encoding="utf-8"))[
            "results"
        ]
    }
    assert set(after) == set(before) and len(after) >= 50, "not the same captures"
    assert all(r.get("status") == 200 or r["id"] in {"employer-applicants"} for r in after.values())
    home, matches = ("home", "light", "en"), ("matches", "light", "en")
    assert before[home]["screens"] > 7 and after[home]["screens"] < before[home]["screens"] - 1
    assert before[matches]["screens"] > 14 and after[matches]["screens"] < 6
    # The framework band moved to About, which got longer by about that much.
    assert after[("about", "light", "en")]["screens"] > before[("about", "light", "en")]["screens"]
    assert all(r["textUnder12px"] == 0 for r in after.values())
    for pictured in (
        "sprint70.home.light.en.jpg",
        "sprint70.home.hi.hi.jpg",
        "sprint70.matches.light.en.jpg",
        "sprint70.matches.hi.hi.jpg",
        "sprint70.about.light.en.jpg",
        "sprint70.app-home-signed-in.light.en.jpg",
        "sprint70.app-matches.light.en.jpg",
    ):
        assert (SCREENS / pictured).is_file(), pictured
