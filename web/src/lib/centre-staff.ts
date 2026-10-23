import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { apiErrorFrom } from "@/lib/http";

export type CentreStaff = components["schemas"]["CentreStaffOut"];
export type StaffInvitation = components["schemas"]["InvitationOut"];

/** Who runs one centre: its own key, so inviting or removing refreshes this and nothing else. */
export const centreStaffKey = (org: string, centre: string) =>
  ["org-centre-staff", org, centre] as const;

export function useCentreStaff(org: string, centre: string) {
  return useQuery({
    queryKey: centreStaffKey(org, centre),
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/org/{org_slug}/centres/{centre_slug}/managers",
        { params: { path: { org_slug: org, centre_slug: centre } } },
      );
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
    retry: false,
  });
}

/** Ask, withdraw, remove. Each throws `ApiError` with what the server said (a duplicate, a cap, a closed centre). */
export function useCentreStaffMutations(org: string, centre: string) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: centreStaffKey(org, centre) });
  const path = { org_slug: org, centre_slug: centre };

  const invite = useMutation({
    mutationFn: async (email: string) => {
      const { data, error, response } = await api.POST(
        "/org/{org_slug}/centres/{centre_slug}/managers",
        { params: { path }, body: { email: email.trim().toLowerCase() } },
      );
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: refresh,
  });

  const revoke = useMutation({
    mutationFn: async (invitationId: string) => {
      const { error, response } = await api.DELETE(
        "/org/{org_slug}/centres/{centre_slug}/managers/invitations/{invitation_id}",
        { params: { path: { ...path, invitation_id: invitationId } } },
      );
      if (error) throw apiErrorFrom(response.status, error);
    },
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: async (userId: string) => {
      const { error, response } = await api.DELETE(
        "/org/{org_slug}/centres/{centre_slug}/managers/{user_id}",
        { params: { path: { ...path, user_id: userId } } },
      );
      if (error) throw apiErrorFrom(response.status, error);
    },
    onSuccess: refresh,
  });

  return { invite, revoke, remove };
}
