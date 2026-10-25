import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { apiErrorFrom } from "@/lib/http";

export type Batch = components["schemas"]["BatchOut"];
export type BatchPhase = Batch["phase"];
export type BatchInput = components["schemas"]["BatchIn"];
export type BatchChanges = components["schemas"]["BatchUpdateIn"];
export type DeliverableCourse = components["schemas"]["DeliverableCourseOut"];
export type BatchOverview = components["schemas"]["BatchOverview"];
export type CourseBatchesRow = components["schemas"]["CourseBatchesRowOut"];

/** Every phase the server can say, in the order a list is filtered by them. Typed over the union. */
export const BATCH_PHASES = [
  "draft",
  "open",
  "full",
  "running",
  "finished",
  "cancelled",
] as const satisfies readonly BatchPhase[];

export const BATCH_PAGE = 25;

/** The one prefix every batch read and write shares, so a change refreshes the lists and nothing else. */
export const batchesKey = (org: string) => ["org-batches", org] as const;

/**
 * An organisation's batches, a page at a time. **`total` is the server's count of what matches**, so
 * "Show more (n left)" is exact and a count is never read off the rows loaded so far.
 */
export function useBatches(org: string, phase: BatchPhase | "") {
  return useInfiniteQuery({
    queryKey: [...batchesKey(org), "list", phase] as const,
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const { data, error, response } = await api.GET("/org/{org_slug}/batches", {
        params: {
          path: { org_slug: org },
          query: { phase: phase || undefined, limit: BATCH_PAGE, offset: pageParam },
        },
      });
      // The status, so `isSignedOut` and a 403 ("this organisation does not deliver training") can
      // be told apart from an outage by the screen.
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    getNextPageParam: (last, all) => {
      const loaded = all.reduce((n, page) => n + page.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
    retry: false,
  });
}

/** The courses a batch can be made of: the organisation's own, and those it is authorised to deliver. */
export function useDeliverableCourses(org: string, enabled = true) {
  return useQuery({
    queryKey: [...batchesKey(org), "courses"] as const,
    enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/batches/courses", {
        params: { path: { org_slug: org } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

/** Plan, change, publish and cancel. Each throws `ApiError` with what the server said. */
export function useBatchMutations(org: string) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: batchesKey(org) });
  const path = { org_slug: org };

  const create = useMutation({
    mutationFn: async (body: BatchInput) => {
      const { data, error, response } = await api.POST("/org/{org_slug}/batches", {
        params: { path },
        body,
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const update = useMutation({
    mutationFn: async (v: { id: string; body: BatchChanges }) => {
      const { data, error, response } = await api.PUT("/org/{org_slug}/batches/{batch_id}", {
        params: { path: { ...path, batch_id: v.id } },
        body: v.body,
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const publish = useMutation({
    mutationFn: async (id: string) => {
      const { data, error, response } = await api.POST("/org/{org_slug}/batches/{batch_id}/publish", {
        params: { path: { ...path, batch_id: id } },
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const cancel = useMutation({
    mutationFn: async (id: string) => {
      const { data, error, response } = await api.POST("/org/{org_slug}/batches/{batch_id}/cancel", {
        params: { path: { ...path, batch_id: id } },
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  return { create, update, publish, cancel };
}

/** What to look at today: counts first, then the next few that start. */
export function useBatchOverview(org: string) {
  return useQuery({
    queryKey: [...batchesKey(org), "overview"] as const,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/batches/overview", {
        params: { path: { org_slug: org } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

/** How other organisations run this seller's courses: counts only, never a learner. */
export function useBatchesOfMyCourses(org: string, enabled = true) {
  return useQuery({
    queryKey: ["org-batches-of-my-courses", org] as const,
    enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/batches/of-my-courses", {
        params: { path: { org_slug: org } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

// ---------------------------------------------------------------------- Sprint 100: the learner

export type PublicBatch = components["schemas"]["PublicBatchOut"];
export type BatchInterest = components["schemas"]["BatchInterestOut"];
export type BatchLearner = components["schemas"]["BatchLearnerOut"];
export type BatchInterestStatus = BatchInterest["status"];
export type CentreStatus = components["schemas"]["CentreStatusIn"]["status"];
export type Reach = PublicBatch["reach"];

export type PublicFilters = {
  stateId: string;
  districtId: string;
  startsWithin: string;
  maxFee: string;
  mode: string;
  course?: string;
};

export const PUBLIC_PAGE = 12;

/** One prefix for every public batch read, so registering or withdrawing refreshes the lists. */
export const PUBLIC_BATCHES = ["public-batches"] as const;
export const MY_BATCH_INTERESTS = ["me", "batch-interests"] as const;

/**
 * The public list of batches, nearest first (the server orders by reach, then start, then fee).
 * **`total` is the server's count of what matches**, so "Show more (n left)" is exact.
 */
export function usePublicBatches(filters: PublicFilters, signedIn: boolean, limit = PUBLIC_PAGE) {
  return useInfiniteQuery({
    // Signed in or not is part of the key: the same list carries the caller's own interests.
    queryKey: [...PUBLIC_BATCHES, filters, signedIn, limit] as const,
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const { data, error, response } = await api.GET("/batches", {
        params: {
          query: {
            state_id: filters.stateId || undefined,
            district_id: filters.districtId || undefined,
            starts_within: filters.startsWithin ? Number(filters.startsWithin) : undefined,
            max_fee: filters.maxFee ? Number(filters.maxFee) : undefined,
            mode: (filters.mode || undefined) as PublicBatch["mode"] | undefined,
            course: filters.course || undefined,
            limit,
            offset: pageParam,
          },
        },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    getNextPageParam: (last, all) => {
      const loaded = all.reduce((n, page) => n + page.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
    retry: false,
  });
}

export function useMyBatchInterests(enabled: boolean) {
  return useQuery({
    queryKey: MY_BATCH_INTERESTS,
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET("/me/batch-interests");
      if (error || !data) throw new Error("batch interests failed");
      return data;
    },
    retry: false,
  });
}

/** Register and withdraw. Each throws `ApiError` with what the server said. */
export function useBatchInterestMutations() {
  const qc = useQueryClient();
  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: PUBLIC_BATCHES }),
      qc.invalidateQueries({ queryKey: MY_BATCH_INTERESTS }),
    ]);
  };
  const register = useMutation({
    mutationFn: async (v: { batchId: string; message: string | null }) => {
      const { data, error, response } = await api.POST("/me/batch-interests", {
        body: { batch_id: v.batchId, message: v.message },
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });
  const withdraw = useMutation({
    mutationFn: async (interestId: string) => {
      const { data, error, response } = await api.POST("/me/batch-interests/{interest_id}/withdraw", {
        params: { path: { interest_id: interestId } },
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });
  return { register, withdraw };
}

/** The learners of one batch, as the centre and its organisation's owners and admins see them. */
export function useBatchLearners(org: string, batchId: string, enabled = true) {
  return useQuery({
    queryKey: [...batchesKey(org), "learners", batchId] as const,
    enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/batches/{batch_id}/learners", {
        params: { path: { org_slug: org, batch_id: batchId } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

export function useSetLearnerStatus(org: string, batchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { interestId: string; status: CentreStatus }) => {
      const { data, error, response } = await api.PATCH(
        "/org/{org_slug}/batches/{batch_id}/learners/{interest_id}",
        {
          params: { path: { org_slug: org, batch_id: batchId, interest_id: v.interestId } },
          body: { status: v.status },
        },
      );
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    // The seats and the counts on the card, the figures on the home and the learners themselves.
    onSuccess: () => qc.invalidateQueries({ queryKey: batchesKey(org) }),
  });
}
