"""Measure the matcher against hand-labelled expectations.

Built before any weight was tuned, because a golden set written afterwards
measures the tuning rather than the behaviour.

**Expectations are relative, never absolute.** "This candidate ranks above that
one" survives a change to the weights; "this candidate scores 82" does not, and
a suite that fails on every deliberate improvement is one people stop running.

Exit code is non-zero when an expectation fails, so this can gate CI.
"""

import asyncio
import sys

from seed_candidates import GOLDEN_PAIRS
from sqlalchemy import select

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateProfile
from api.modules.matching.service import match_job_by_slug, match_jobs


async def _profile_for(db, phone: str):
    user = await db.scalar(select(User).where(User.phone == phone))
    if user is None:
        return None
    return await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))


async def main() -> None:
    failures: list[str] = []
    lines: list[str] = []

    async with get_sessionmaker()() as db:
        scores: dict[tuple[str, str], int] = {}

        for phone, slug, expectation in GOLDEN_PAIRS:
            profile = await _profile_for(db, phone)
            if profile is None:
                failures.append(f"{phone}: no profile. Run scripts/seed_candidates.py")
                continue

            scored = await match_job_by_slug(db, profile.id, slug)
            if scored is None:
                failures.append(f"{phone} -> {slug}: job not found")
                continue
            result = scored.result
            scores[(phone, slug)] = result.score
            lines.append(
                f"  {phone[-4:]}  {slug:<34} score={result.score:>3}  "
                f"matched={len(result.matched)}  missing={len(result.missing)}"
                f"{'  CAPPED' if result.capped_by_mandatory else ''}"
            )

            if expectation == "capped_missing_mandatory":
                if result.missing_mandatory == 0:
                    failures.append(f"{phone} -> {slug}: expected a missing mandatory standard")
                elif not result.capped_by_mandatory:
                    failures.append(
                        f"{phone} -> {slug}: missing a mandatory standard but the score "
                        f"was not capped"
                    )
            elif expectation == "not_ranked":
                if result.score != 0:
                    failures.append(
                        f"{phone} -> {slug}: shares no standard but scored {result.score}"
                    )
                ranked = await match_jobs(db, profile.id, limit=20)
                if any(r.job.slug == slug for r in ranked):
                    failures.append(f"{phone}: {slug} should not appear in their ranking")
            elif expectation == "top":
                ranked = await match_jobs(db, profile.id, limit=5)
                if not ranked:
                    failures.append(f"{phone}: expected {slug} to rank first, got nothing")
                elif ranked[0].job.slug != slug:
                    failures.append(
                        f"{phone}: expected {slug} first, got {ranked[0].job.slug} "
                        f"({ranked[0].result.score})"
                    )

        # Relative orderings, which is what a golden set can defend.
        gda = "general-duty-assistant-chennai"
        complete = scores.get(("+919000000001", gda))
        capped = scores.get(("+919000000002", gda))
        declared = scores.get(("+919000000003", gda))

        if complete is not None and capped is not None and not complete > capped:
            failures.append(
                f"a candidate holding every mandatory standard ({complete}) must outrank "
                f"one missing one ({capped})"
            )
        if complete is not None and declared is not None and not complete > declared:
            failures.append(
                f"assessed and certified evidence ({complete}) must outrank the same "
                f"standards self-declared ({declared})"
            )

    print("\n".join(lines))
    print()
    if failures:
        print(f"{len(failures)} expectation(s) failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        await dispose_engine()
        raise SystemExit(1)

    print(f"all {len(GOLDEN_PAIRS)} golden pairs and 2 orderings hold.")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
