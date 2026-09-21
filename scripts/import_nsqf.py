"""Project the NSQF corpus from MongoDB into PostgreSQL.

    make import-nsqf

Idempotent: re-running updates in place and picks up any revisions published
since the last run. MongoDB remains the source of record (ADR-034).
"""

import asyncio
import sys
import time

from api.adapters.nsqf.importer import import_nsqf
from api.adapters.nsqf.mongo import MongoNsqfSource
from api.core.database import dispose_engine, get_sessionmaker


async def main() -> int:
    started = time.perf_counter()
    source = MongoNsqfSource()
    try:
        async with get_sessionmaker()() as db:
            report = await import_nsqf(db, source)
    finally:
        await source.close()
        await dispose_engine()

    print(report.summary())
    print(f"elapsed: {time.perf_counter() - started:.1f}s")

    if report.problems:
        print(f"\n{len(report.problems)} record(s) could not be imported:", file=sys.stderr)
        for problem in report.problems[:20]:
            print(
                f"  [{problem.collection}] {problem.identifier}: {problem.reason}",
                file=sys.stderr,
            )
        if len(report.problems) > 20:
            print(f"  ... and {len(report.problems) - 20} more", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
