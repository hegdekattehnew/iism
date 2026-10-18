"""Fold a browser run's small-control counts into the recorded baseline (Sprint 78, BL-19.9).

The browser sweep holds every page to a count of controls under 44 px that **may only go down**
(`web/e2e/support/target-baseline.json`). To record counts, run the sweep with the log switched on
and fold the log in:

    rm -f /tmp/iism-targets.jsonl
    cd web && TARGETS_LOG=/tmp/iism-targets.jsonl npx playwright test e2e/sweep.spec.ts
    .venv/bin/python scripts/merge_target_baseline.py /tmp/iism-targets.jsonl

A page already recorded keeps the **lower** of the two numbers, so recording after a regression
cannot raise a ceiling by accident; a page not yet recorded is added. `--allow-raise LABEL` is the
one way up, for a page whose design genuinely gained a control, and it names the page so the diff
says so. Without the log switch a run **checks** instead of recording (`checkPage`'s `ratchet`).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "web" / "e2e" / "support" / "target-baseline.json"


_RUN_ID = re.compile(r"\b[0-9a-f]{8}\b")


def normalise(label: str) -> str:
    """A page made for the run has a random id in its slug: record the page, not the run."""
    return _RUN_ID.sub("<id>", label)


def merge(
    baseline: dict[str, int], lines: list[str], allow_raise: set[str] | None = None
) -> dict[str, int]:
    """The baseline after folding in a log: new pages added, known pages only ever lowered."""
    allow_raise = allow_raise or set()
    out = dict(baseline)
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        label, count = normalise(row["label"]), row["count"]
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"{label}: a count must be a whole number, got {count!r}")
        if label not in out or count < out[label] or label in allow_raise:
            out[label] = count
    return dict(sorted(out.items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--allow-raise", action="append", default=[], metavar="LABEL")
    args = parser.parse_args()
    lines = args.log.read_text(encoding="utf-8").splitlines()
    if not lines:
        print("the log is empty: nothing ran with TARGETS_LOG set", file=sys.stderr)
        return 1
    before = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    after = merge(before, lines, set(args.allow_raise))
    BASELINE.write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
    added = len(after) - len(before)
    lowered = sum(1 for k in before if after[k] < before[k])
    print(f"{len(after)} pages recorded ({added} added, {lowered} lowered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
