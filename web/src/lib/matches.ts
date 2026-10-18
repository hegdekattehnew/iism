import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useMemberships } from "@/lib/org";

/** How many matches arrive at once: the route's maximum. */
export const MATCHES_FETCH = 50;

/**
 * The signed-in job seeker's ranked matches. **One query, one key** (`["matches"]`), read by the
 * matches page and by the job lists (Sprint 84, BL-19.15), so a visit to both asks the server once and
 * a mutation that invalidates `["matches"]` refreshes both.
 */
export async function fetchMatches() {
  const { data, error } = await api.GET("/me/matches", { params: { query: { limit: MATCHES_FETCH } } });
  // openapi-fetch resolves rather than throws on a non-2xx, so without this a 401 arrives as
  // `data: undefined` and renders as "nothing matches" -- telling a signed-out visitor they have no
  // matches rather than that they are not signed in.
  if (error || !data) throw new Error("matches request failed");
  return data;
}

/**
 * The match score for each vacancy the person has one for, by slug (UI-04): what a job card shows when
 * the person is a signed-in job seeker. **Silent otherwise**: a visitor, or an organisation-only
 * account, asks nothing (`/me/matches` would answer 403/404 and log an error), and a failed request
 * only means no score is shown. A vacancy outside the top `MATCHES_FETCH` has no entry, and a card
 * with no score says nothing about it (it is not "0%").
 */
export function useMyScores(): { scores: ReadonlyMap<string, number>; isSeeker: boolean } {
  const { isJobSeeker } = useMemberships();
  const matches = useQuery({
    queryKey: ["matches"],
    enabled: isJobSeeker,
    queryFn: fetchMatches,
    retry: false,
  });
  const scores = new Map<string, number>();
  for (const m of matches.data?.items ?? []) scores.set(m.job.slug, m.score);
  return { scores, isSeeker: isJobSeeker };
}
