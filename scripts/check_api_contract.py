"""Check, or record, the API contract the released mobile app depends on (Sprint 62, ADR-072).

    .venv/bin/python scripts/check_api_contract.py            # CI: fail on a breaking change
    .venv/bin/python scripts/check_api_contract.py --update   # add newly listed operations
    .venv/bin/python scripts/check_api_contract.py --release  # re-record all (a store release)

The operations are listed in `mobile/contract/surface.txt`; the snapshot is
`mobile/contract/openapi.snapshot.json`. `--update` only **adds** operations the snapshot lacks, so
it can never hide a break; `--release` replaces every entry and is what cutting a store build does,
after the minimum app version has been raised if a retired build must stop being served.
"""

import argparse
import json
import sys
from pathlib import Path

from api.core.contract import (
    ContractError,
    breaking_changes,
    snapshot,
    surface_operations,
    widened_enums,
)

ROOT = Path(__file__).resolve().parent.parent
SURFACE = ROOT / "mobile" / "contract" / "surface.txt"
SNAPSHOT = ROOT / "mobile" / "contract" / "openapi.snapshot.json"


def _write(data: dict[str, object]) -> None:
    SNAPSHOT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="add operations the snapshot lacks")
    mode.add_argument("--release", action="store_true", help="re-record every operation")
    args = parser.parse_args()

    from api.main import app  # imported late: it assembles the whole application

    try:
        current = snapshot(app.openapi(), surface_operations(SURFACE.read_text(encoding="utf-8")))
    except ContractError as error:
        print(f"contract: {error}", file=sys.stderr)
        return 1

    recorded: dict[str, object] = (
        json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    )

    if args.release:
        _write(current)
        print(f"contract: recorded {len(current)} operations for this release")
        return 0

    missing = sorted(set(current) - set(recorded))
    if args.update:
        _write({**recorded, **{key: current[key] for key in missing}})
        print(f"contract: added {len(missing)} operation(s): {', '.join(missing) or 'none'}")
        return 0

    problems = breaking_changes(recorded, current)  # type: ignore[arg-type]
    for note in widened_enums(recorded, current):  # type: ignore[arg-type]
        print(f"contract: note (not a failure): {note}")
    if missing:
        problems.append(
            "not yet recorded: "
            + ", ".join(missing)
            + " (run `make snapshot-contract` in the change that adds them)"
        )
    if problems:
        print("contract: this would break the released mobile app:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "Keep the old shape and add the new one beside it, or raise MOBILE_MIN_VERSION_* and "
            "re-record with --release (ADR-072).",
            file=sys.stderr,
        )
        return 1
    print(f"contract: {len(recorded)} mobile operation(s) unchanged for the released app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
