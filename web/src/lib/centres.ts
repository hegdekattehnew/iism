import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { apiErrorFrom } from "@/lib/http";

export type Centre = components["schemas"]["CentreOut"];
export type CentreInput = components["schemas"]["CentreIn"];

/** The one key every centre read and write shares, so a change refreshes the list and nothing else. */
export const centresKey = (org: string) => ["org-centres", org] as const;

export function useCentres(org: string, enabled = true) {
  return useQuery({
    queryKey: centresKey(org),
    enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/centres", {
        params: { path: { org_slug: org } },
      });
      // The status, so `isSignedOut` and a 403 ("this organisation does not deliver training") can
      // be told apart from an outage by the screen.
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

/** Create, change, close and reopen. Each throws `ApiError` with what the server said. */
export function useCentreMutations(org: string) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: centresKey(org) });
  const path = { org_slug: org };

  const create = useMutation({
    mutationFn: async (body: CentreInput) => {
      const { data, error, response } = await api.POST("/org/{org_slug}/centres", {
        params: { path },
        body,
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const update = useMutation({
    mutationFn: async (v: { slug: string; body: CentreInput }) => {
      const { data, error, response } = await api.PUT("/org/{org_slug}/centres/{centre_slug}", {
        params: { path: { ...path, centre_slug: v.slug } },
        body: v.body,
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const close = useMutation({
    mutationFn: async (slug: string) => {
      const { data, error, response } = await api.POST(
        "/org/{org_slug}/centres/{centre_slug}/close",
        { params: { path: { ...path, centre_slug: slug } } },
      );
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const reopen = useMutation({
    mutationFn: async (slug: string) => {
      const { data, error, response } = await api.POST(
        "/org/{org_slug}/centres/{centre_slug}/reopen",
        { params: { path: { ...path, centre_slug: slug } } },
      );
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  return { create, update, close, reopen };
}

export type ManagedCentre = components["schemas"]["ManagedCentreOut"];

/** The centre a manager runs: one key, so saving refreshes the page and nothing else. */
export const myCentreKey = (slug: string) => ["my-centre", slug] as const;

export function useMyCentre(slug: string) {
  return useQuery({
    queryKey: myCentreKey(slug),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/centre", {
        params: { path: { org_slug: slug } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

export function useUpdateMyCentre(slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CentreInput) => {
      const { data, error, response } = await api.PUT("/org/{org_slug}/centre", {
        params: { path: { org_slug: slug } },
        body,
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: (data) => qc.setQueryData(myCentreKey(slug), data),
  });
}

/** Who else runs the centre, as any member of it may read (a colleague's name and address). */
export function useCentreColleagues(slug: string) {
  return useQuery({
    queryKey: ["my-centre", slug, "members"] as const,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/members", {
        params: { path: { org_slug: slug } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}
