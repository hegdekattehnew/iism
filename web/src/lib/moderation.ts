"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "./api-schema";
import { api } from "./api";
import { apiErrorFrom } from "./http";

export type ReportReason = components["schemas"]["ReportIn"]["reason"];
export type TargetType =
  components["schemas"]["ListingReportsOut"]["target_type"];
export type ListingReports = components["schemas"]["ListingReportsOut"];
export type ReportQueue = components["schemas"]["ReportQueueOut"];
export type QueueView = "open" | "taken_down";

/** Mirrored from `ReportIn.detail`, `DismissIn.note` and `TakedownIn.reason`;
 *  `lib/constraints.test.ts` pins them against the server's source. */
export const DETAIL_MAX = 1000;
export const NOTE_MIN = 10;
export const NOTE_MAX = 1000;

export const REASONS: ReportReason[] = [
  "asks_for_money",
  "fake_or_misleading",
  "discriminatory",
  "unsafe_or_illegal",
  "spam_or_duplicate",
  "other",
];

const QUEUE = ["ops", "reports"] as const;

/**
 * Tell us a listing is wrong (Sprint 59, BL-14.4). The failure keeps what the server said: "you
 * manage this listing" and "you have already reported it" are 409s a person can act on, and a 429
 * says when to come back.
 */
export function useReportListing(kind: TargetType, slug: string) {
  return useMutation({
    mutationFn: async (input: { reason: ReportReason; detail?: string }) => {
      const body = { reason: input.reason, detail: input.detail || undefined };
      const result =
        kind === "job"
          ? await api.POST("/jobs/{slug}/report", {
              params: { path: { slug } },
              body,
            })
          : await api.POST("/courses/{slug}/report", {
              params: { path: { slug } },
              body,
            });
      if (!result.data) {
        throw apiErrorFrom(result.response.status, result.error);
      }
      return result.data;
    },
  });
}

export function useReportQueue(view: QueueView) {
  return useQuery({
    queryKey: [...QUEUE, view] as const,
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/ops/reports", {
        params: { query: { view } },
      });
      if (error || !data)
        throw apiErrorFrom(response.status, error);
      return data;
    },
  });
}

export type Decision =
  | { kind: "dismiss"; note: string }
  | { kind: "takedown"; reason: string }
  | { kind: "restore" };

export function useDecideListing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (
      input: { target: TargetType; id: string } & Decision,
    ) => {
      const path = { target_type: input.target, target_id: input.id };
      const result =
        input.kind === "dismiss"
          ? await api.POST("/ops/reports/{target_type}/{target_id}/dismiss", {
              params: { path },
              body: { note: input.note },
            })
          : input.kind === "takedown"
            ? await api.POST(
                "/ops/listings/{target_type}/{target_id}/takedown",
                {
                  params: { path },
                  body: { reason: input.reason },
                },
              )
            : await api.POST(
                "/ops/listings/{target_type}/{target_id}/restore",
                {
                  params: { path },
                },
              );
      if (!result.data)
        throw apiErrorFrom(result.response.status, result.error);
      return result.data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: QUEUE });
    },
  });
}
