"""Verify `role_aliases.py` against the real corpus.

Editing that file is "verified by running this, against the real corpus", as its
own docstring says, but for twenty sprints nothing ran it, and what it checked
was only that a target exists. `alias_problems()` (`api/modules/skills/service.py`)
now checks three things that make an alias wrong, and reports a fourth that makes
one ambiguous:

* **A target that names nothing.** The alias matches nothing, silently.
* **A target whose representative pack is disability-track** (a `PWD/` code). The
  rule is "point at the general pack". Fourteen keys had broken it for twenty
  sprints because the role names carried no "Divyangjan" tag, so no check could see it.
* **A key that is itself a role's exact title but is aliased elsewhere**, so
  typing a title in full would send somebody to a different role.
* *(reported, never a failure)* every prefix of three or more characters that two
  or more targets claim. Role search is a typeahead, so some ambiguity is expected;
  it has to be known, not hidden.

Needs the real NSQF import (`make import-nsqf`), not the ephemeral test database:
the targets are real qualification-pack job roles, which the pytest suite's
hand-built fixtures do not contain. Same reason `make evaluate` is a standalone
script rather than a pytest test. The rule logic itself is covered by
`tests/test_role_search_trust.py` on a fixture corpus.
"""

import asyncio
import sys

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.skills.role_aliases import MIN_ALIAS_PREFIX
from api.modules.skills.service import alias_problems

# Longer collisions are almost always one key beside another that is a longer
# spelling of the same thing ("data entry" and "data entry operator").
SHORT = MIN_ALIAS_PREFIX + 1


async def main() -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        report = await alias_problems(db)
    await dispose_engine()

    if report.unresolved:
        print(f"{len(report.unresolved)} target(s) name no current qualification:")
        for target in report.unresolved:
            print(f"  {target!r}")
    if report.disability_track:
        print(f"{len(report.disability_track)} alias(es) resolve to a disability-track pack:")
        for key, target, code in report.disability_track:
            print(f"  {key!r} -> {target!r} ({code})")
    if report.shadowed:
        print(f"{len(report.shadowed)} key(s) are a role's exact title but aliased elsewhere:")
        for key, _ in report.shadowed:
            print(f"  {key!r}")

    short = {p: t for p, t in report.prefix_collisions.items() if len(p) <= SHORT}
    if short:
        print(f"\nNot failures: {len(short)} short prefix(es) claimed by more than one role:")
        for prefix, targets in short.items():
            print(f"  {prefix!r}: {', '.join(targets)}")

    if report.failures:
        return 1
    print("\nEvery role_aliases.py target names a real, current, general qualification.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
