"""Hold the mobile app's size to a ceiling (Sprint 66, ADR-077).

    .venv/bin/python scripts/check_mobile_budget.py [--export-dir /tmp/iism-export]

The target device is a low-end Android on mobile data. The ceilings in `mobile/budget.json` are a
**ceiling, not a target**: they stop the app growing unnoticed, the way the web's first-load budget
does. The bundle measured is the Android **Hermes bytecode** that `expo export` writes (what a phone
downloads and loads), and the assets are the files in `mobile/assets`. No launch time is measured
here: that needs a device. Stdlib only, so the mobile CI job can run it without the Python project.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOBILE = ROOT / "mobile"
BUDGET = MOBILE / "budget.json"


def measure(export_dir: Path, assets_dir: Path) -> dict[str, int]:
    bundles = sorted((export_dir / "_expo" / "static" / "js" / "android").glob("*.hbc"))
    if len(bundles) != 1:
        raise FileNotFoundError(
            f"expected one Android .hbc bundle in {export_dir}, found {len(bundles)}"
        )
    assets = [p for p in assets_dir.iterdir() if p.is_file()]
    if not assets:
        raise FileNotFoundError(f"no assets in {assets_dir}")
    return {
        "android_bundle_bytes": bundles[0].stat().st_size,
        "assets_bytes": sum(p.stat().st_size for p in assets),
    }


def over_budget(measured: dict[str, int], ceilings: dict[str, int]) -> list[str]:
    """What is over, naming both numbers; a ceiling with nothing measured against it is a defect."""
    problems = []
    for name, ceiling in ceilings.items():
        if name not in measured:
            problems.append(f"{name}: a ceiling with nothing measured against it")
        elif measured[name] > ceiling:
            problems.append(f"{name}: {measured[name]:,} bytes is over the ceiling of {ceiling:,}")
    for name in measured:
        if name not in ceilings:
            problems.append(f"{name}: measured but has no ceiling in mobile/budget.json")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path, default=Path("/tmp/iism-export"))
    args = parser.parse_args()
    try:
        data = json.loads(BUDGET.read_text(encoding="utf-8"))
        ceilings = {k: v for k, v in data.items() if isinstance(v, int)}
        measured = measure(args.export_dir, MOBILE / "assets")
    except (OSError, ValueError) as error:
        print(f"budget: {error}", file=sys.stderr)
        return 1
    for name, value in measured.items():
        print(f"{name}: {value:,} of {ceilings.get(name, 0):,}")
    problems = over_budget(measured, ceilings)
    for problem in problems:
        print(f"OVER  {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
