import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { apiErrorFrom } from "@/lib/http";

export type Centre = components["schemas"]["CentreOut"];
export type CentreInput = components["schemas"]["CentreIn"];

/** The one key every centre read and write shares, so a change refreshes the list and nothing else. */
export const centresKey = (org: string) => ["org-centres", org] as const;

export function useCentres(org: string) {
  return useQuery({
    queryKey: centresKey(org),
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
