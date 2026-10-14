"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";

import type { components } from "./api-schema";
import { api } from "./api";
import { ApiError, readDetail } from "./http";
import { NOTICES } from "./unread-count";

export type Notice = components["schemas"]["NotificationOut"];

export const PAGE_SIZE = 30;

/** Every notice, newest first, a page at a time; the cursor is the last one's time **and** id. */
export function useNoticePages(signedIn: boolean) {
  return useInfiniteQuery({
    queryKey: [...NOTICES, "pages"] as const,
    enabled: signedIn,
    retry: false,
    initialPageParam: null as { before: string; before_id: string } | null,
    queryFn: async ({ pageParam }) => {
      const { data, error, response } = await api.GET("/me/notifications", {
        params: { query: { limit: PAGE_SIZE, ...(pageParam ?? {}) } },
      });
      const status = response.status;
      if (error || !data) throw new ApiError(status, readDetail(error));
      return data;
    },
    getNextPageParam: (last) =>
      last.length < PAGE_SIZE
        ? undefined
        : {
            before: last[last.length - 1].created_at,
            before_id: last[last.length - 1].id,
          },
  });
}

export function useReadOne() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.POST(
        "/me/notifications/{notification_id}/read",
        {
          params: { path: { notification_id: id } },
        },
      );
      const status = response.status;
      if (error) throw new ApiError(status, readDetail(error));
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: NOTICES });
    },
  });
}

export function useReadAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST("/me/notifications/read");
      const status = response.status;
      if (error) throw new ApiError(status, readDetail(error));
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: NOTICES });
    },
  });
}
