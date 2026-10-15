"""The ADR register workbook names every ADR (Sprint 67).

`docs/adr/IISM-ADR-Register.xlsx` is built from the ADR file by
`scripts/build_adr_register.py`. A new ADR without a rebuilt register would make the shareable index
quietly stale, which is exactly what it exists to prevent, so this fails until it is regenerated.
"""

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADRS = ROOT / "docs" / "adr" / "architecture-decisions.md"
REGISTER = ROOT / "docs" / "adr" / "IISM-ADR-Register.xlsx"


def _ids_in_the_document() -> list[str]:
    return re.findall(r"^## (ADR-\d+):", ADRS.read_text(encoding="utf-8"), re.M)


def _ids_in_the_register() -> list[str]:
    sheet = zipfile.ZipFile(REGISTER).read("xl/worksheets/sheet2.xml").decode("utf-8")
    # Column A only: other columns name related ADRs, which are not rows.
    return re.findall(r'<c r="A\d+"[^>]*><is><t[^>]*>(ADR-\d{3})</t>', sheet)


def test_the_register_names_every_adr_once() -> None:
    document = _ids_in_the_document()
    assert len(document) >= 78  # found them before judging any
    assert _ids_in_the_register() == document, (
        "the ADR register is out of date: run `.venv/bin/python scripts/build_adr_register.py`"
    )


def test_four_headers_that_read_plain_accepted_now_say_what_changed() -> None:
    text = ADRS.read_text(encoding="utf-8")
    for adr, later in (
        ("019", "ADR-040"),
        ("032", "ADR-038"),
        ("033", "ADR-041"),
        ("037", "ADR-038"),
    ):
        head = re.search(rf"^## ADR-{adr}:.*?\n\n(\*\*Status:\*\*[^\n]*)", text, re.S | re.M)
        assert head, adr
        assert "Superseded in part by " + later in head.group(1), (
            f"ADR-{adr} header: {head.group(1)}"
        )
