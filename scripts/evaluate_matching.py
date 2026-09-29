"""Measure the matcher against hand-labelled expectations.

Built before any weight was tuned, because a golden set written afterwards
measures the tuning rather than the behaviour.

**Expectations are relative, never absolute.** "This candidate ranks above that
one" survives a change to the weights; "this candidate scores 82" does not, and
a suite that fails on every deliberate improvement is one people stop running.

Three kinds of expectation, because they answer different questions:

* `GOLDEN_PAIRS` -- a property of one candidate against one vacancy.
* `GOLDEN_ORDERINGS` -- "this one must outrank that one", which is the only
  shape that can defend a weighting.
* `GOLDEN_COURSE_PAIRS` -- what `courses_closing_gap` must suggest. ADR-025
  names course recommendation as one of three metrics standing in for a revenue
  signal while v1 is free; until Sprint 29 it had no labelled data at all.

**An unrecognised expectation is a failure, not a no-op.** `below_assessed_peer`
sat in the set for nineteen sprints with no branch to handle it: the chain had
three arms and no `else`, so that pair asserted nothing while the summary line
counted it as holding.

Exit code is non-zero when an expectation fails, so this can gate CI.
"""

import asyncio
import sys

from seed_candidates import GOLDEN_COURSE_PAIRS, GOLDEN_ORDERINGS, GOLDEN_PAIRS
from sqlalchemy import select

from api.core.database import dispose_engine, get_sessionmaker
from api.modules.identity.models import User
from api.modules.marketplace.models import CandidateProfile
from api.modules.matching.service import courses_closing_gap, match_job_by_slug, match_jobs

# How far down a "ranked" expectation may look. Five is what the candidate
# actually sees above the fold; a larger window would make the claim weaker
# than the screen it describes.
RANKED_WITHIN = 5


async def _profile_for(db, phone: str):
    user = await db.scalar(select(User).where(User.phone == phone))
    if user is None:
        return None
    return await db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))


async def _score(db, phone: str, slug: str, scores: dict, failures: list[str]) -> int | None:  # type: ignore[no-untyped-def]
    """This pair's score, computed once and reused.

    An ordering may name a candidate that no `GOLDEN_PAIRS` row covers, so this
    scores on demand rather than reading a cache that may not have been filled
    -- the failure mode the hard-coded version had.
    """
    if (phone, slug) in scores:
        return scores[(phone, slug)]
    profile = await _profile_for(db, phone)
    if profile is None:
        failures.append(f"{phone}: no profile. Run scripts/seed_candidates.py")
        return None
    scored = await match_job_by_slug(db, profile.id, slug)
    if scored is None:
        failures.append(f"{phone} -> {slug}: job not found")
        return None
    scores[(phone, slug)] = scored.result.score
    return scored.result.score


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
            elif expectation == "missing_mandatory":
                # The weaker half of the same rule: the ceiling holds even for
                # a candidate who was never going to reach it. `capped` is
                # `raw > MANDATORY_GAP_CAP`, so it is False for them and
                # asserting it would be asserting the wrong thing.
                if result.missing_mandatory == 0:
                    failures.append(f"{phone} -> {slug}: expected a missing mandatory standard")
                elif result.score > 45:
                    failures.append(
                        f"{phone} -> {slug}: missing a mandatory standard and scored "
                        f"{result.score}, above the ceiling"
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
            elif expectation == "ranked":
                # The weaker claim, for a candidate whose two best vacancies
                # are genuinely close. Over-claiming `top` there is how a
                # golden set starts failing on deliberate improvements.
                ranked = await match_jobs(db, profile.id, limit=RANKED_WITHIN)
                if not any(r.job.slug == slug for r in ranked):
                    got = ", ".join(r.job.slug for r in ranked) or "nothing"
                    failures.append(
                        f"{phone}: expected {slug} within the top {RANKED_WITHIN}, got {got}"
                    )
            else:
                # The guard that was missing. An unrecognised label used to
                # fall through all three arms in silence while the summary
                # counted it as holding.
                failures.append(f"{phone} -> {slug}: unknown expectation {expectation!r}")

        # Relative orderings, which is what a golden set can actually defend.
        # Read from the table rather than hard-coded phones: the previous
        # version named `+919000000001` inline, so removing a pair from
        # `GOLDEN_PAIRS` made the ordering check silently pass on a `None`.
        for better, worse, slug, why in GOLDEN_ORDERINGS:
            a = await _score(db, better, slug, scores, failures)
            b = await _score(db, worse, slug, scores, failures)
            if a is None or b is None:
                continue
            if not a > b:
                failures.append(f"{slug}: {why} -- {better[-4:]}={a}, {worse[-4:]}={b}")

        # What `courses_closing_gap` must say about a gap. ADR-025's metric,
        # labelled for the first time.
        for phone, slug, expectation in GOLDEN_COURSE_PAIRS:
            profile = await _profile_for(db, phone)
            if profile is None:
                failures.append(f"{phone}: no profile. Run scripts/seed_candidates.py")
                continue
            scored = await match_job_by_slug(db, profile.id, slug)
            if scored is None:
                failures.append(f"{phone} -> {slug}: job not found")
                continue
            suggestions = await courses_closing_gap(db, scored.result.missing)
            slugs = [s.course.slug for s in suggestions]

            if expectation == "closes_mandatory":
                if not suggestions:
                    failures.append(f"{phone} -> {slug}: a gap with nothing offered to close it")
                elif suggestions[0].covers_mandatory < 1:
                    # The function's own sort promises this: a course that
                    # unblocks an application beats one that merely improves
                    # a score.
                    failures.append(
                        f"{phone} -> {slug}: top suggestion {slugs[0]} covers no mandatory gap"
                    )
            elif expectation.startswith("suggests:"):
                wanted = expectation.split(":", 1)[1]
                if wanted not in slugs:
                    failures.append(
                        f"{phone} -> {slug}: expected {wanted} among the suggestions, "
                        f"got {', '.join(slugs) or 'nothing'}"
                    )
            elif expectation == "no_suggestions":
                if suggestions:
                    failures.append(f"{phone} -> {slug}: no gap, but offered {', '.join(slugs)}")
            else:
                failures.append(f"{phone} -> {slug}: unknown course expectation {expectation!r}")

    print("\n".join(lines))
    print()
    if failures:
        print(f"{len(failures)} expectation(s) failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        await dispose_engine()
        raise SystemExit(1)

    print(
        f"all {len(GOLDEN_PAIRS)} golden pairs, {len(GOLDEN_ORDERINGS)} orderings "
        f"and {len(GOLDEN_COURSE_PAIRS)} course expectations hold."
    )
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
