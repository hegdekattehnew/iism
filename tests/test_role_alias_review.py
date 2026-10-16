"""The reviewer's workbook is the alias list as it stands (Sprint 71).

It is built from `ROLE_ALIASES` alone, so a stale copy is detectable without the corpus: the
committed workbook must carry every surface form and the same cells the builder writes now.
"""

import importlib.util
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "docs" / "IISM-Role-Aliases-for-Review.xlsx"


def _builder():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "build_role_alias_review", ROOT / "scripts" / "build_role_alias_review.py"
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_the_workbook_is_built_from_the_alias_list() -> None:
    m = _builder()
    sheets = m.build_sheets()
    assert len(m.ROLE_ALIASES) >= 250  # found them before judging any
    z = zipfile.ZipFile(BOOK)
    for i, (_, xml) in enumerate(sheets):
        assert z.read(f"xl/worksheets/sheet{i + 1}.xml").decode("utf-8") == xml, (
            "docs/IISM-Role-Aliases-for-Review.xlsx is stale: "
            "run `.venv/bin/python scripts/build_role_alias_review.py`"
        )


def test_every_alias_has_a_row_and_a_blank_decision() -> None:
    m = _builder()
    from xlsx_min import esc  # on sys.path once _builder has run

    rows = zipfile.ZipFile(BOOK).read("xl/worksheets/sheet2.xml").decode("utf-8")
    for surface in m.ROLE_ALIASES:
        assert f">{esc(surface)}<" in rows, surface
    # The decision column is the reviewer's: nothing is pre-filled as kept.
    assert rows.count("Keep / change / retire") == 1
    for decision in (">keep<", ">Keep<", ">retire<", ">Retire<"):
        assert decision not in rows


def test_the_summary_says_the_batch_is_unreviewed() -> None:
    summary = zipfile.ZipFile(BOOK).read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "UNREVIEWED" in summary


def test_script_detection_can_tell_the_scripts_apart() -> None:
    m = _builder()
    assert m.language("वेल्डर") == "Devanagari"
    assert m.language("welder") == "Latin script"
    assert m.language("bijli mistri") == "Latin script"
