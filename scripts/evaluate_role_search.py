"""Score role search against the titles people type (Sprint 71, BL-12.12).

    make evaluate-roles

Role search is the door to everything a job seeker gets, and its vocabulary is a table of aliases
nobody had measured. `tests/fixtures/role_titles.json` holds about 150 titles (English, Hinglish,
Devanagari) with the corpus roles that honestly fit each, written **before** any alias was added and
**not** from what the search answered; this runs `search_roles` for every one and says how often the
right role is first and how often it is in the first three, by wording and by split.

* **`tune`** titles were used to write aliases and to decide any ranking change.
* **`hold`** titles were not. Read the hold-out line **once, at the end**: a number you tuned
  against measures the tuning. Their per-title lines are hidden unless `--show-hold` is passed,
  so a miss there cannot quietly become the next alias (the first run printed them, and the
  sprint's record says so).
* **`none_ok`** titles are jobs the corpus has no honest role for ("waiter": only disability-track
  or manager-level packs exist). The right answer is not to lead with a wrong one, so they pass
  unless the first result is one of the roles listed under `reject` or a disability-track pack
  (`PWD/`).

Like `make evaluate`, it needs the real NSQF import (`make import-nsqf`); the pytest suite's fixture
corpus has nine invented codes, so CI holds only the *shape* of the fixture
(`tests/test_role_titles.py`), which is also where `judge` is tested. It reads, never writes.
"""

import asyncio
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "role_titles.json"

# A corpus this small is the test fixture, not the national one.
MIN_CORPUS_ROLES = 1000


@dataclass(frozen=True)
class Outcome:
    query: str
    kind: str
    split: str
    none_ok: bool
    passed: bool
    rank: (
        int | None
    )  # 1-based position of the first accepted role within the top ten; None if absent
    top1: str | None


def _key(name: str) -> str:
    return " ".join(name.lower().split())


def accepted_roles(case: dict[str, Any], corpus: list[str]) -> set[str]:
    """Pure: the roles that honestly fit a title.

    Its exact `accept` names plus every corpus role whose name matches one of its `accept_like`
    patterns (written from the job's meaning, not from results).
    """
    patterns = [re.compile(p, re.IGNORECASE) for p in case.get("accept_like", [])]
    found = {_key(r) for r in corpus if any(p.search(r) for p in patterns)}
    return found | {_key(r) for r in case.get("accept", [])}


def judge(
    case: dict[str, Any], hits: list[tuple[str, str]], accepted: set[str] | None = None
) -> Outcome:
    """Pure: one title's outcome from the roles search returned, as `(job_role, qp_code)` in order.

    A title with an answer passes when an accepted role is among the first three, and records its
    rank. `accepted` is `accepted_roles(...)`; without it only the exact `accept` names count.
    A `none_ok` title passes unless the first result is a rejected role or a disability-track
    pack: having nothing, or something unrelated, is acceptable; leading with a wrong confident
    one is not.
    """
    top1 = hits[0][0] if hits else None
    if case.get("none_ok"):
        reject = {_key(r) for r in case.get("reject", [])}
        bad = bool(hits) and (_key(hits[0][0]) in reject or hits[0][1].startswith("PWD/"))
        return Outcome(case["query"], case["kind"], case["split"], True, not bad, None, top1)
    accepted = accepted if accepted is not None else {_key(r) for r in case.get("accept", [])}
    rank = next((i for i, (role, _) in enumerate(hits[:10], 1) if _key(role) in accepted), None)
    return Outcome(
        case["query"],
        case["kind"],
        case["split"],
        False,
        rank is not None and rank <= 3,
        rank,
        top1,
    )


def summarise(outcomes: list[Outcome]) -> dict[str, dict[str, float | int]]:
    """Top-1 and top-3 rates over the titles that have an answer, by split and by wording."""
    groups: dict[str, list[Outcome]] = defaultdict(list)
    for o in outcomes:
        if o.none_ok:
            continue
        groups["all"].append(o)
        groups[f"split:{o.split}"].append(o)
        groups[f"kind:{o.kind}"].append(o)
    return {
        name: {
            "titles": len(items),
            "top1": sum(1 for o in items if o.rank == 1) / len(items),
            "top3": sum(1 for o in items if o.rank is not None and o.rank <= 3) / len(items),
        }
        for name, items in sorted(groups.items())
    }


async def main(argv: list[str]) -> int:
    from sqlalchemy import func, select

    from api.core.database import dispose_engine, get_sessionmaker
    from api.modules.skills import search_roles
    from api.modules.skills.hierarchy import QualificationPack

    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    verbose = "--quiet" not in argv
    # The hold-out is read once, at the end: per-title lines for it are hidden unless asked for, so
    # a miss there cannot quietly become the next alias. The summary line is always printed.
    show_hold = "--show-hold" in argv
    sessionmaker = get_sessionmaker()
    outcomes: list[Outcome] = []
    async with sessionmaker() as db:
        roles = await db.scalar(select(func.count()).select_from(QualificationPack))
        if (roles or 0) < MIN_CORPUS_ROLES:
            print(
                f"only {roles} qualification packs: this needs the real corpus (make import-nsqf)"
            )
            return 2
        corpus = sorted(
            {
                r
                for r in (
                    await db.scalars(
                        select(QualificationPack.job_role).where(QualificationPack.is_current)
                    )
                ).all()
                if r
            }
        )
        known = {_key(r) for r in corpus}
        unknown = sorted(
            {
                a
                for c in cases
                for a in [*c.get("accept", []), *c.get("reject", [])]
                if _key(a) not in known
            }
        )
        if unknown:
            print(f"{len(unknown)} accepted or rejected role(s) name nothing in the corpus:")
            for name in unknown:
                print(f"  {name}")
            return 1
        for case in cases:
            accepted = accepted_roles(case, corpus)
            if not case.get("none_ok") and not accepted:
                print(f"nothing in the corpus fits {case['query']!r}: its patterns match no role")
                return 1
            found = await search_roles(db, case["query"], limit=10)
            outcomes.append(judge(case, [(h.job_role, h.qp_code) for h in found], accepted))
    await dispose_engine()

    if verbose:
        for o in outcomes:
            if o.split == "hold" and not show_hold:
                continue
            mark = "ok  " if o.passed else "MISS"
            where = "none_ok" if o.none_ok else (f"rank {o.rank}" if o.rank else "absent")
            print(f"{mark} [{o.split}/{o.kind[:3]}] {o.query:26} {where:8} -> {o.top1}")
    print()
    for name, row in summarise(outcomes).items():
        print(
            f"{name:18} {row['titles']:4} titles   "
            f"top-1 {row['top1']:6.1%}   top-3 {row['top3']:6.1%}"
        )
    none = [o for o in outcomes if o.none_ok]
    print(f"\nno honest role exists ({len(none)}): {sum(o.passed for o in none)} not led astray")
    for o in none:
        print(f"  {'ok  ' if o.passed else 'MISS'} {o.query:14} -> {o.top1}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
