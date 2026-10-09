"""Seed the database the browser tests run against (Sprint 52, ADR-062).

    make seed-e2e

CI has no 21,303-standard corpus -- it lives in MongoDB, which is not in the repository -- so
the browser journeys run on `tests/fixtures/nsqf_sample.json`: nine invented standards, three
roles and a little real geography (Karnataka / Bengaluru Urban, Assam / Dhubri). It goes through
the same `JsonFileNsqfSource` and `import_nsqf` the test suite uses, so the journeys exercise the
real import path rather than a second loader.

This deliberately does **not** run `seed_marketplace.py` or `seed_candidates.py`: they fail loudly
without the real codes, and the journeys make their own organisations, vacancies and candidates
through the product, which is the thing under test.

**It refuses to run against anything but a database whose name ends in `_e2e`.** The importer
deletes and rewrites the standards it owns, which on the development database would replace the
real corpus with nine invented rows. `make seed-e2e` creates `iism_e2e` and points here.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.engine import make_url

from api.adapters.nsqf.importer import import_nsqf
from api.adapters.nsqf.jsonfile import JsonFileNsqfSource
from api.core.config import get_settings
from api.core.database import dispose_engine, get_sessionmaker
from api.modules.marketplace.models import Course, Job
from api.modules.skills.alias_admin import sync_seed_aliases
from api.modules.skills.role_aliases import ROLE_ALIASES

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "nsqf_sample.json"


def _guard() -> str:
    name = make_url(get_settings().database_url).database or ""
    if not name.endswith("_e2e"):
        raise SystemExit(
            f"refusing to seed {name!r}: the browser-test seed replaces the NSQF corpus and only "
            "runs against a database whose name ends in '_e2e'. Use `make seed-e2e`, which "
            "creates iism_e2e."
        )
    return name


async def clear_listings() -> int:
    """Delete every vacancy and course (and, by cascade, what hangs off them).

    The browser tests run against one long-lived database, and a journey that ranks vacancies --
    `/matches` shows a top twenty -- is crowded out by the identical ones earlier runs left behind
    (all tied at the same score). Standards, geography and aliases stay: that is the corpus.
    """
    name = _guard()
    try:
        async with get_sessionmaker()() as db:
            jobs = (await db.execute(delete(Job))).rowcount
            courses = (await db.execute(delete(Course))).rowcount
            await db.commit()
    finally:
        await dispose_engine()
    print(f"cleared {jobs} vacancies and {courses} courses from {name}")
    return 0


async def main() -> int:
    name = _guard()
    try:
        async with get_sessionmaker()() as db:
            report = await import_nsqf(db, JsonFileNsqfSource(FIXTURE))
            await db.commit()
            # Role search reads the alias table, not the dict. Only the aliases whose role the
            # fixture holds can resolve ("ward boy" -> General Duty Assistant does).
            sync = await sync_seed_aliases(db, ROLE_ALIASES)
    finally:
        await dispose_engine()
    print(f"seeded {name} from {FIXTURE.name}")
    print(report.summary())
    print(f"role aliases: {sync.added} added, {sync.updated} updated")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clear-listings",
        action="store_true",
        help="delete vacancies and courses, keep the corpus",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(clear_listings() if args.clear_listings else main()))
