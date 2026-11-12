"""Build `docs/design/plain-levels-for-review.md`: the reader's copy of the words for a level.

A job seeker is told "Skilled worker, level 4" where the framework says "NSQF level 4" (Sprint
104, BL-22.5). The words were written by an engineer and **nobody who knows the work has read
them**; this file is what to hand to someone who does, one row per step, in every language the
product has, with empty columns for what to keep, change or retire. It is built from the catalogue
(`web/src/messages`), so it cannot drift from what a person is shown, and
`tests/test_level_words.py` fails when it is stale.

Run: `.venv/bin/python scripts/build_level_words_review.py`
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = ROOT / "web" / "src" / "messages"
OUT = ROOT / "docs" / "design" / "plain-levels-for-review.md"
LOCALES = (("en", "English"), ("hi", "Hindi"), ("ms", "Malay (English until translated)"))


def _levels(locale: str) -> dict:
    return json.loads((MESSAGES / f"{locale}.json").read_text(encoding="utf-8"))["levels"]


def render() -> str:
    tables = {code: _levels(code) for code, _ in LOCALES}
    out = [
        "# Plain levels: the words, for a reader who knows the work",
        "",
        '**Status: UNREVIEWED.** These words stand in for "NSQF level n" on a vacancy, a course, a '
        "standard, a search result, a match and a career path (Sprint 104, BL-22.5). They were "
        'written by the engineer. The number always stays beside them ("Skilled worker, level '
        '4"), so a wrong word never hides the fact, but a wrong word is still wrong.',
        "",
        "A half level (2.5, 3.5, 4.5, 5.5, 6.5) is real and is said as the space between its two "
        'neighbours ("Skilled worker to senior skilled worker, level 4.5"); it has no line of its '
        "own. The words live in `web/src/messages/{en,hi,ms}.json` under `levels`; change them "
        "there, then run `.venv/bin/python scripts/build_level_words_review.py`.",
        "",
        "Please mark each row **keep**, **change** (and to what) or **retire**, in the last "
        "column, and say whether the *line* is true of someone at that step in the work you know.",
        "",
    ]
    for code, label in LOCALES:
        table = tables[code]
        out += [
            f"## {label}",
            "",
            "| Level | Name | One line | Keep / change / retire |",
            "|---|---|---|---|",
        ]
        for step in range(1, 11):
            out.append(f"| {step} | {table['name'][f'l{step}']} | {table['line'][f'l{step}']} | |")
        out += [
            "",
            f"Half level, joined: `{table['between']}`. With the number: `{table['labelled']}`. "
            f"A vacancy's floor: `{table['orAbove']}`.",
            "",
        ]
    return "\n".join(out)


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
