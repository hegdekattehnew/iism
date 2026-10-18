"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "./api-schema";
import { api } from "./api";
import { apiErrorFrom, failedWith, type WaitError } from "./http";

export type GrievanceKind = components["schemas"]["GrievanceIn"]["kind"];
export type GrievanceStatus = components["schemas"]["GrievanceOut"]["status"];
export type Submitted = components["schemas"]["GrievanceSubmittedOut"];
export type MyGrievance = components["schemas"]["GrievanceOut"];
export type QueueItem = components["schemas"]["GrievanceQueueItem"];

/** Mirrored from `GrievanceIn.body` / `GrievanceDecisionIn.note`; `lib/constraints.test.ts` pins them. */
export const BODY_MIN = 10;
export const BODY_MAX = 4000;
export const REPLY_TO_MAX = 254;
export const NOTE_MIN = 10;
export const NOTE_MAX = 1000;

const MINE = ["me", "grievances"] as const;
const QUEUE = ["ops", "grievances"] as const;

/**
 * Send a message to us (Sprint 57, BL-14.3, ADR-067).
 *
 * The failure keeps what the server said: a 429 carries how long to wait, a 401 on a data request
 * means "sign in", and a 422 names the field. `website` is the honeypot, always sent empty by a
 * person and never shown.
 */
export function useSendGrievance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      kind: GrievanceKind;
      body: string;
      reply_to?: string;
      website?: string;
    }): Promise<Submitted> => {
      const { data, error, response } = await api.POST("/grievances", {
        body: input,
      });
      if (!data) {
        const failure: WaitError = failedWith(response);
        throw Object.assign(apiErrorFrom(response.status, error), {
          retryAfter: failure.retryAfter,
        });
      }
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: MINE });
    },
  });
}

/** The signed-in person's own messages and where each stands. */
export function useMyGrievances(enabled: boolean) {
  return useQuery({
    queryKey: MINE,
    enabled,
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/me/grievances");
      // Read before the check: this route declares no error body, so `response` narrows to
      // `never` inside the branch.
      const status = response.status;
      if (error || !data) throw apiErrorFrom(status, error);
      return data;
    },
  });
}

export function useGrievanceQueue(status: GrievanceStatus | "all") {
  return useQuery({
    queryKey: [...QUEUE, status] as const,
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/ops/grievances", {
        params: { query: status === "all" ? {} : { status } },
      });
      if (error || !data)
        throw apiErrorFrom(response.status, error);
      return data;
    },
  });
}

export type Decision = "acknowledge" | "resolve" | "dismiss";

export function useDecideGrievance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      id: string;
      decision: Decision;
      note?: string;
    }) => {
      const params = { path: { grievance_id: input.id } };
      const result =
        input.decision === "acknowledge"
          ? await api.POST("/ops/grievances/{grievance_id}/acknowledge", {
              params,
            })
          : input.decision === "resolve"
            ? await api.POST("/ops/grievances/{grievance_id}/resolve", {
                params,
                body: { note: input.note ?? "" },
              })
            : await api.POST("/ops/grievances/{grievance_id}/dismiss", {
                params,
                body: { note: input.note ?? "" },
              });
      if (!result.data)
        throw apiErrorFrom(result.response.status, result.error);
      return result.data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: QUEUE });
    },
  });
}
