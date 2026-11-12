"""Plain levels (Sprint 104, BL-22.5): the one rule both clients run, and the reader's copy.

`tests/fixtures/level_cases.json` says which step of the ladder a level is; the web's and the
phone's tests both read it, and a client that stopped reading it would pass on cases of its own.
The words themselves are messages in three languages, and
`docs/design/plain-levels-for-review.md` is built from them so that the one person who can say
whether they are right is shown what a seeker is shown.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "tests" / "fixtures" / "level_cases.json"


def _build():
    spec = importlib.util.spec_from_file_location(
        "build_level_words_review", ROOT / "scripts" / "build_level_words_review.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_cases_are_well_formed_and_cover_each_kind_of_answer() -> None:
    cases = json.loads(CASES.read_text())["cases"]
    assert len(cases) >= 12
    kinds = {None if c["expect"] is None else c["expect"]["kind"] for c in cases}
    assert kinds == {"whole", "between", None}, "a step, the space between two, and no level"
    for c in cases:
        assert {"name", "level", "shown", "expect"} <= set(c)
    wholes = {c["expect"]["step"] for c in cases if c["expect"] and c["expect"]["kind"] == "whole"}
    assert {1, 4, 10} <= wholes, "both ends of the ladder and the middle"
    halves = [c for c in cases if c["expect"] and c["expect"]["kind"] == "between"]
    assert all(c["expect"]["upper"] == c["expect"]["lower"] + 1 for c in halves)


def test_both_clients_read_the_file() -> None:
    for reader in ("web/src/lib/level-words.test.ts", "mobile/src/test/level-words.test.ts"):
        assert "level_cases.json" in (ROOT / reader).read_text(), reader


def test_the_two_clients_run_one_rule() -> None:
    web = (ROOT / "web/src/lib/level-words.ts").read_text()
    phone = (ROOT / "mobile/src/core/level-words.ts").read_text()

    def code(text: str) -> str:
        # The rule, not the comments around it (the phone's header says it is the web's).
        body = text.split("export type LevelStops", 1)[1]
        return "\n".join(
            line for line in body.splitlines() if not line.strip().startswith(("*", "/*", "//"))
        )

    assert code(web) == code(phone)


def test_every_language_has_every_step() -> None:
    for locale in ("en", "hi", "ms"):
        levels = json.loads((ROOT / f"web/src/messages/{locale}.json").read_text(encoding="utf-8"))[
            "levels"
        ]
        assert [f"l{n}" for n in range(1, 11)] == list(levels["name"]), locale
        assert [f"l{n}" for n in range(1, 11)] == list(levels["line"]), locale
        assert "NSQF" not in json.dumps(levels, ensure_ascii=False), locale


def test_the_readers_copy_is_the_catalogue() -> None:
    build = _build()
    path = ROOT / "docs" / "design" / "plain-levels-for-review.md"
    assert path.read_text(encoding="utf-8") == build.render(), (
        "run `.venv/bin/python scripts/build_level_words_review.py`"
    )
    text = path.read_text(encoding="utf-8")
    assert "UNREVIEWED" in text, "it says plainly that nobody who knows the work has read it"
    assert "Skilled worker" in text and "कुशल कामगार" in text
