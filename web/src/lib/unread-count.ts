"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "./api";
import { apiErrorFrom } from "./http";

/** Everything under this prefix is the notice list or the count, so one invalidation moves both. */
export const NOTICES = ["me", "notifications"] as const;

/**
 * The header's unread count (Sprint 60, BL-14.9).
 *
 * **Asked only by somebody signed in**: a signed-out visitor makes no request that can only answer
 * 401 (Sprint 52). Not polled: it is refreshed when the person comes back to the tab, which is when
 * a count is worth looking at, and the page itself invalidates it whenever a notice is opened.
 */
export function useUnreadCount(signedIn: boolean): number {
  const query = useQuery({
    queryKey: [...NOTICES, "count"] as const,
    enabled: signedIn,
    retry: false,
    staleTime: 30_000,
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/me/notifications/unread-count",
      );
      // Read before the check: this route declares no error body.
      const status = response.status;
      if (error || !data) throw apiErrorFrom(status, error);
      return data.unread;
    },
  });
  return query.data ?? 0;
}
