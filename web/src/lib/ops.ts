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
export type PlatformDashboard =
  paths["/ops/dashboard"]["get"]["responses"]["200"]["content"]["application/json"];
export type ProgrammeReport =
  paths["/ops/programmes/{name}"]["get"]["responses"]["200"]["content"]["application/json"];

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

export function useOperatorDashboard() {
  return useQuery({
    queryKey: ["ops", "dashboard"] as const,
    retry: false,
    queryFn: async () => {
      // Status read before the check, not inside it: this route takes no
      // parameters at all, so its schema carries only a 200 -- on the
      // failure branch openapi-fetch narrows the whole result to `never` and
      // `response` becomes unreachable there (`useMemberships`'s own fix for
      // `/auth/me`, the same shape).
      const result = await api.GET("/ops/dashboard", {});
      const status = result.response.status;
      const errorBody: unknown = result.error;
      if (errorBody || !result.data) throw new ApiError(status, readDetail(errorBody));
      return result.data;
    },
  });
}

export function useKnownProgrammes() {
  return useQuery({
    queryKey: ["ops", "programmes"] as const,
    retry: false,
    queryFn: async () => {
      const result = await api.GET("/ops/programmes", {});
      const status = result.response.status;
      const errorBody: unknown = result.error;
      if (errorBody || !result.data) throw new ApiError(status, readDetail(errorBody));
      return result.data.programmes;
    },
  });
}

export function useProgrammeReport(programme: string | null) {
  return useQuery({
    queryKey: ["ops", "programme", programme] as const,
    enabled: programme !== null,
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/ops/programmes/{name}", {
        params: { path: { name: programme as string } },
      });
      if (error || !data) throw new ApiError(response.status, readDetail(error));
      return data;
    },
  });
}

/**
 * A programme's enrolment by district (Sprint 40) -- a separate, heavier
 * query from `useProgrammeReport`'s own four numbers, fetched only once a
 * programme is actually chosen and only for the district section, never
 * folded into the base report's payload.
 */
export function useProgrammeDistricts(programme: string | null) {
  return useQuery({
    queryKey: ["ops", "programme", programme, "districts"] as const,
    enabled: programme !== null,
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/ops/programmes/{name}/districts", {
        params: { path: { name: programme as string } },
      });
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
