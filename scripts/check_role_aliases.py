"""Verify every `role_aliases.py` target names a real, current qualification.

`unresolved_aliases()` (`api/modules/skills/service.py`) has existed since
Sprint 23 for exactly this -- the file's own docstring says editing it is
"verified by running this, against the real corpus" -- but nothing has ever
actually run it. A stale or mistyped value "matches nothing, silently," which
is precisely the class of mistake this catches instead.

Needs the real NSQF import (`make import-nsqf`), not the ephemeral test
database: the alias targets are real qualification-pack job roles, which the
pytest suite's hand-built fixtures do not contain. Same reason `make evaluate`
is a standalone script rather than a pytest test.
"""

import asyncio
import sys

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.skills.service import unresolved_aliases


async def main() -> int:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as db:
        unresolved = await unresolved_aliases(db)
    await dispose_engine()

    if unresolved:
        print(f"{len(unresolved)} role_aliases.py target(s) name no current qualification:")
        for target in unresolved:
            print(f"  {target!r}")
        return 1

    print("Every role_aliases.py target names a real, current qualification.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
