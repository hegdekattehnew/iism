"""Copy the web app's message catalogues into the mobile app (Sprint 62, ADR-072).

One set of words, read by both clients. The mobile copy is **generated**, never edited: edit
`web/src/messages/*.json` and run `make sync-mobile-messages`. `tests/test_mobile_foundations.py`
fails when the two differ, naming this command, so a translation fixed on one side cannot quietly
stay broken on the other.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "web" / "src" / "messages"
TARGET = ROOT / "mobile" / "src" / "messages"
MOBILE = ROOT / "mobile"

# `useTranslations("matchesPage")` or `useTranslations("mobile.list")`: the first word is the
# top-level namespace of the catalogue. `mobile` is the phone's own, in `app.*.json`.
_NAMESPACE = re.compile(r'useTranslations\(\s*"(\w+)')


def namespaces_used() -> set[str]:
    """The web namespaces a phone screen reads, found in the phone's own sources.

    **The phone carries only these** (Sprint 102): the catalogue was copied whole, and the website's
    words for the back office, the employer's workspace, the footer and the rest were 70 percent of
    two JSON files in a bundle with 19 KB to spare. Derived from the sources rather than listed by
    hand, so a screen that starts using a namespace brings it with it and nobody has to remember.
    Tests are left out: a test reads what a screen reads.
    """
    found: set[str] = set()
    for folder in ("src", "app"):
        for path in sorted((MOBILE / folder).rglob("*.ts*")):
            name = path.name
            if ".test." in name or "/test/" in path.as_posix() or "messages" in path.parts:
                continue
            if name == "schema.d.ts":
                continue
            found.update(_NAMESPACE.findall(path.read_text(encoding="utf-8")))
    found.discard("mobile")
    return found


def subset(catalogue: dict[str, object], used: set[str]) -> dict[str, object]:
    return {name: value for name, value in catalogue.items() if name in used}


def rendered(catalogue: dict[str, object]) -> str:
    """The file text, as the web files have it: two-space indent, real Unicode, a final newline."""
    return json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    used = namespaces_used()
    copied = 0
    for path in sorted(SOURCE.glob("*.json")):
        if path.name == "fatal.json":
            continue  # the web's own last-resort error page; nothing on a phone reads it
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        (TARGET / path.name).write_text(rendered(subset(catalogue, used)), encoding="utf-8")
        copied += 1
    if not copied:
        print(f"no catalogues found in {SOURCE}", file=sys.stderr)
        return 1
    print(f"copied {copied} catalogue(s) ({len(used)} namespaces) to {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
