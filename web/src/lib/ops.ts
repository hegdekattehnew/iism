"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { paths } from "./api-schema";
import { api } from "./api";
import { ApiError, readDetail } from "./http";

export type QueueRow =
  paths["/ops/organisations"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type VerificationDetail =
  paths["/ops/organisations/{org_slug}/verification"]["get"]["responses"]["200"]["content"]["application/json"];
export type Decision = "granted" | "revoked";

/**
 * The back office's data layer.
 *
 * A parallel to `lib/org.ts` rather than a reuse of it, for the reason that
 * module is a parallel to `lib/profile.ts`: the shapes differ. An organisation
 * here is a *subject*, not something the caller belongs to, so nothing is keyed
 * on an active context and there is no membership to read.
 *
 * **404 is the normal refusal.** `require_operator` answers a non-operator with
 * a body byte-identical to an unrouted path (ADR-042), so these queries must
 * not translate a 404 into "something went wrong" -- it means "not yours", and
 * the page renders not-found rather than an error.
 */

/** The note's floor, mirrored from `VerificationIn.note` and pinned by
 *  `lib/constraints.test.ts`. The browser refuses before a request is made. */
export const NOTE_MIN = 10;
export const NOTE_MAX = 500;

const QUEUE = ["ops", "queue"] as const;
const detailKey = (slug: string) => ["ops", "organisation", slug] as const;

export function useVerificationQueue() {
  return useQuery({
    queryKey: QUEUE,
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/ops/organisations", {});
      if (error || !data) throw new ApiError(response.status, readDetail(error));
      return data;
    },
  });
}

export function useVerificationDetail(slug: string) {
  return useQuery({
    queryKey: detailKey(slug),
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/ops/organisations/{org_slug}/verification",
        { params: { path: { org_slug: slug } } },
      );
      if (error || !data) throw new ApiError(response.status, readDetail(error));
      return data;
    },
  });
}

export function useSetVerification(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ decision, note }: { decision: Decision; note: string }) => {
      const { data, error, response } = await api.POST(
        "/ops/organisations/{org_slug}/verification",
        { params: { path: { org_slug: slug } }, body: { decision, note } },
      );
      // The server names the field and the reason; a fixed sentence here would
      // throw that away, which this project has a shipped defect about.
      if (error || !data) throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: (data) => {
      // Replace rather than invalidate: the response *is* the new detail, and
      // a refetch would show the old badge for a beat on a slow connection.
      qc.setQueryData(detailKey(slug), data);
      // The queue is a different question -- a verified organisation leaves it
      // -- so that one is invalidated.
      void qc.invalidateQueries({ queryKey: QUEUE });
    },
  });
}
