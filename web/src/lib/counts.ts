/**
 * The public catalogue counts, and the one place their query keys live.
 *
 * "Every number below is counted live from the platform database" is a claim
 * the homepage makes in its own subtitle, so a figure older than the thing it
 * counts is not a slow refresh -- it is the page saying something untrue.
 *
 * Publishing a vacancy, unpublishing one, closing it, deleting it, the same
 * four for a course, and deleting the organisation that holds any of them all
 * change these numbers. None of them invalidated anything: the mutations
 * refreshed `["org-jobs", slug]` and stopped there, so an employer who
 * published a vacancy and clicked back to the homepage was shown the count
 * fetched before they did it.
 *
 * The keys are exported rather than spelled out at each site because four
 * files read them and three write them. A renamed string would still compile,
 * still pass `tsc`, and simply stop invalidating -- the rename that keeps
 * compiling is the kind that ships.
 */

import type { QueryClient } from "@tanstack/react-query";

/** `/marketplace/counts` -- the jobs and courses figures on the homepage panels. */
export const MARKETPLACE_COUNTS = ["marketplace-counts"] as const;

/** `/marketplace/stats` -- the corpus band, which also carries jobs and courses. */
export const CORPUS_STATS = ["corpus-stats"] as const;

/** `/skills/count`. Only the NSQF importer moves this, so nothing invalidates it. */
export const SKILL_COUNT = ["skill-count"] as const;

/**
 * Mark the public counts stale after changing what they count.
 *
 * Fire-and-forget by design: a refetch that fails must never be the reason a
 * publish reports failure to the employer who just succeeded at it.
 */
export function invalidatePublicCounts(qc: QueryClient): void {
  void qc.invalidateQueries({ queryKey: MARKETPLACE_COUNTS });
  void qc.invalidateQueries({ queryKey: CORPUS_STATS });
}
