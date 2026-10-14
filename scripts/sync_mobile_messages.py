"""Copy the web app's message catalogues into the mobile app (Sprint 62, ADR-072).

One set of words, read by both clients. The mobile copy is **generated**, never edited: edit
`web/src/messages/*.json` and run `make sync-mobile-messages`. `tests/test_mobile_foundations.py`
fails when the two differ, naming this command, so a translation fixed on one side cannot quietly
stay broken on the other.
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "web" / "src" / "messages"
TARGET = ROOT / "mobile" / "src" / "messages"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(SOURCE.glob("*.json")):
        if path.name == "fatal.json":
            continue  # the web's own last-resort error page; nothing on a phone reads it
        shutil.copyfile(path, TARGET / path.name)
        copied += 1
    if not copied:
        print(f"no catalogues found in {SOURCE}", file=sys.stderr)
        return 1
    print(f"copied {copied} catalogue(s) to {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
