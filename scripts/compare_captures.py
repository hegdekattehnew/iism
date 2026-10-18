"""A before-and-after table, per page family, from two runs of the review's capture script.

    .venv/bin/python scripts/compare_captures.py BEFORE/measurements.json AFTER/measurements.json

`web/scripts/capture-review.mjs` measures 52 pages (375x812, light, plus dark, Hindi and desktop for
chosen ones). Epic B19's stories each migrate a *family* of pages, and "did it help" is a question
about the family, so this folds the two runs into one row per family: how many captures, how long in
screens, how many controls under 44 px, how much text under 12 px, how many icons (inline SVGs) and
how many console or network errors. A page in only one run is listed, never silently dropped, and a
run with no captures is a failure (a table of nothing would read as "no change").
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

#: The page ids each family holds (Epic B19, BL-19.15 to 19.20): the revamp moves one at a time.
_FAMILY_PAGES: dict[str, tuple[str, ...]] = {
    "home and discovery": (
        "home",
        "jobs",
        "job-detail",
        "courses",
        "course-detail",
        "search",
        "skills",
    ),
    "sign-in, sign-up and profile": ("signin", "signup", "signup-seeker", "profile"),
    "candidate area": (
        "matches",
        "applications",
        "saved",
        "interests",
        "notifications",
        "account",
        "career-paths",
    ),
    "employer and provider": (
        "employer-home",
        "employer-applicants",
        "employer-candidates",
        "employer-team",
        "employer-upload",
        "provider-home",
        "provider-interests",
        "provider-upload",
    ),
    "back office": ("admin",),
    "static and legal": ("about", "contact", "employers", "providers", "privacy"),
}
#: Page id to family.
FAMILIES: dict[str, str] = {
    page: family for family, pages in _FAMILY_PAGES.items() for page in pages
}
ORDER = [
    "home and discovery",
    "sign-in, sign-up and profile",
    "candidate area",
    "employer and provider",
    "back office",
    "static and legal",
    "(unclassified)",
]


def _key(row: dict) -> tuple:
    return (row["id"], row.get("variant"), row.get("locale"))


def load(path: Path) -> list[dict]:
    rows = [
        r for r in json.loads(path.read_text(encoding="utf-8"))["results"] if not r.get("error")
    ]
    if not rows:
        raise ValueError(f"{path} holds no captures")
    return rows


def summarise(before: list[dict], after: list[dict]) -> tuple[list[dict], list[str]]:
    """One row per family over the captures present in **both** runs, and the keys in only one."""
    b = {_key(r): r for r in before}
    a = {_key(r): r for r in after}
    both = sorted(set(b) & set(a), key=str)
    only = sorted(f"{k[0]}.{k[1]}.{k[2]}" for k in set(b) ^ set(a))
    groups: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for k in both:
        groups[FAMILIES.get(k[0], "(unclassified)")].append((b[k], a[k]))

    def total(pairs: list[tuple[dict, dict]], field: str, side: int) -> float:
        return sum((p[side].get(field) or 0) for p in pairs)

    table = []
    for family in ORDER:
        pairs = groups.get(family)
        if not pairs:
            continue
        table.append(
            {
                "family": family,
                "captures": len(pairs),
                **{
                    f"{field}_{side_name}": round(total(pairs, field, side), 1)
                    for field in ("screens", "smallTargets", "textUnder12px", "svgs")
                    for side, side_name in ((0, "before"), (1, "after"))
                },
                "errors_before": sum(len(p[0].get("errors") or []) for p in pairs),
                "errors_after": sum(len(p[1].get("errors") or []) for p in pairs),
            }
        )
    return table, only


def _pair(row: dict, field: str, width: int) -> str:
    return f"{row[field + '_before']:g} > {row[field + '_after']:g}".rjust(width)


def render(table: list[dict], only: list[str]) -> str:
    columns = f"{'screens':>13}  {'small':>9}  {'tiny':>9}  {'icons':>9}  {'errors':>9}"
    head = f"{'family':<30}{'caps':>5}  {columns}"
    lines = [head, "-" * len(head)]
    for r in table:
        cells = "  ".join(
            [
                _pair(r, "screens", 13),
                _pair(r, "smallTargets", 9),
                _pair(r, "textUnder12px", 9),
                _pair(r, "svgs", 9),
                f"{r['errors_before']} > {r['errors_after']}".rjust(9),
            ]
        )
        lines.append(f"{r['family']:<30}{r['captures']:>5}  {cells}")
    if only:
        lines.append(f"\nin only one run (not compared): {', '.join(only)}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    table, only = summarise(load(Path(argv[1])), load(Path(argv[2])))
    if not table:
        print("the two runs share no capture", file=sys.stderr)
        return 1
    print(render(table, only))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
