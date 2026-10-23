import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { apiErrorFrom } from "@/lib/http";

export type Arrangement = components["schemas"]["AuthorisationOut"];
export type OrgRef = components["schemas"]["OrgRefOut"];

/** One key for an organisation's arrangements, so any act refreshes the list and nothing else. */
export const deliveryKey = (org: string) => ["org-delivery", org] as const;

export function useDelivery(org: string) {
  return useQuery({
    queryKey: deliveryKey(org),
    queryFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/delivery", {
        params: { path: { org_slug: org } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

/** Training organisations by words, optionally only those that sell courses or deliver training. */
export function useOrganisationSearch(q: string, role: "sells" | "delivers", enabled = true) {
  const words = q.trim();
  return useQuery({
    queryKey: ["training-organisations", role, words] as const,
    enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/training-organisations", {
        params: { query: { q: words || undefined, [role]: true, limit: 8 } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

/** The courses an organisation sells, as its public page shows them: the choices of a scope. */
export function useSellerCourses(slug: string | null) {
  return useQuery({
    queryKey: ["seller-courses", slug] as const,
    enabled: slug !== null,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/providers/{slug}", {
        params: { path: { slug: slug as string }, query: { limit: 100 } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data.courses ?? [];
    },
    retry: false,
  });
}

/** Ask, invite, approve, decline, revoke. Each throws `ApiError` with what the server said. */
export function useDeliveryMutations(org: string) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: deliveryKey(org) });
  const path = { org_slug: org };

  const ask = useMutation({
    mutationFn: async (v: { provider: string; course: string | null }) => {
      const { data, error, response } = await api.POST("/org/{org_slug}/delivery/requests", {
        params: { path },
        body: { organisation_slug: v.provider, course_slug: v.course },
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const invite = useMutation({
    mutationFn: async (v: { partner: string; course: string | null }) => {
      const { data, error, response } = await api.POST("/org/{org_slug}/delivery/invitations", {
        params: { path },
        body: { organisation_slug: v.partner, course_slug: v.course },
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const act = useMutation({
    mutationFn: async (v: { id: string; verb: "approve" | "decline" | "revoke" }) => {
      const params = { path: { ...path, authorisation_id: v.id } };
      const { data, error, response } =
        v.verb === "approve"
          ? await api.POST("/org/{org_slug}/delivery/{authorisation_id}/approve", { params })
          : v.verb === "decline"
            ? await api.POST("/org/{org_slug}/delivery/{authorisation_id}/decline", { params })
            : await api.POST("/org/{org_slug}/delivery/{authorisation_id}/revoke", { params });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  return { ask, invite, act };
}
