import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { ApiError, readDetail } from "../core/errors";
import {
  addSkillsBulk,
  applyTo,
  getMatch,
  getProfile,
  listApplications,
  listInterests,
  listMatches,
  listSaved,
  registerInterest,
  removeSkill,
  roleStandards,
  saveJob,
  searchRoleHits,
  unsaveJob,
  updateProfile,
  withdrawApplication,
  withdrawInterest,
  type ProfileUpdate,
} from "../core/me";
import { ME_KEY, meKeys } from "../core/me-keys";
import type { BulkBody } from "../core/role-picker";
import { api, useSignedIn } from "../runtime";

/**
 * The queries and writes about the signed-in candidate. **Every key starts with `"me"`** (see
 * `core/me-keys.ts`): never persisted, and removed when the person signs out.
 *
 * - **A signed-out person makes no request that can only answer 401**: each query waits for
 *   `signedIn`, and the ones that need a job-seeker profile wait for the account to say there is
 *   one (an organisation owner who signed in on a phone would only be told 403).
 * - **Every write is returned whole**, so the screen that pressed the button can read its own
 *   `isError`/`error` and say what the server said. A write that cannot report its failure is the
 *   one the web's `mutation-errors.test.ts` exists to catch; `lib/mutation-errors.test.ts` is its
 *   twin here.
 */

/** Who the server says is signed in, and so whether there is a job-seeker side to show. */
export function useAccount() {
  const signedIn = useSignedIn();
  const query = useQuery({
    queryKey: meKeys.account,
    enabled: signedIn,
    queryFn: async () => {
      // Status read before the check: `/auth/me` documents no error body, so on the failure branch
      // openapi-fetch narrows the whole result to `never` (the web's `useOperatorDashboard`).
      const result = await api.GET("/auth/me");
      const status = result.response.status;
      const errorBody: unknown = result.error;
      if (errorBody || !result.data) throw new ApiError(status, readDetail(errorBody));
      return result.data;
    },
  });
  /** `undefined` until the answer is in: a button that appears and vanishes is worse than a late one. */
  const isJobSeeker = query.data
    ? query.data.memberships?.some((m) => m.tenant.tenant_type === "personal") === true
    : undefined;
  return { signedIn, query, isJobSeeker };
}

/** The gate for everything below: signed in, and the account has a job-seeker side. */
function useSeeker() {
  const { signedIn, isJobSeeker } = useAccount();
  return { signedIn, enabled: signedIn && isJobSeeker === true };
}

export function useProfile() {
  const { enabled } = useSeeker();
  return useQuery({ queryKey: meKeys.profile, enabled, queryFn: () => getProfile(api) });
}

export function useMatches() {
  const { enabled } = useSeeker();
  return useQuery({ queryKey: meKeys.matches, enabled, queryFn: () => listMatches(api) });
}

export function useMatch(slug: string) {
  const { enabled } = useSeeker();
  return useQuery({ queryKey: meKeys.match(slug), enabled, queryFn: () => getMatch(api, slug) });
}

export function useApplications() {
  const { enabled } = useSeeker();
  return useQuery({ queryKey: meKeys.applications, enabled, queryFn: () => listApplications(api) });
}

export function useSaved() {
  const { enabled } = useSeeker();
  return useQuery({ queryKey: meKeys.saved, enabled, queryFn: () => listSaved(api) });
}

export function useInterests() {
  const { enabled } = useSeeker();
  return useQuery({ queryKey: meKeys.interests, enabled, queryFn: () => listInterests(api) });
}

/** Roles matching what the person typed. Nothing is asked until there is something to ask. */
export function useRoleHits(q: string) {
  const { enabled } = useSeeker();
  const term = q.trim();
  return useQuery({
    queryKey: meKeys.roles(term),
    enabled: enabled && term.length > 0,
    queryFn: () => searchRoleHits(api, term),
  });
}

export function useRoleStandards(slug: string | null) {
  const { enabled } = useSeeker();
  return useQuery({
    queryKey: meKeys.roleStandards(slug ?? ""),
    enabled: enabled && slug !== null,
    queryFn: () => roleStandards(api, slug ?? ""),
  });
}

// ------------------------------------------------------------------ writes

/** A skill changes every score, so matches and every open match go stale with the profile. */
function skillsChanged(qc: QueryClient) {
  void qc.invalidateQueries({ queryKey: meKeys.profile });
  void qc.invalidateQueries({ queryKey: meKeys.matches });
  void qc.invalidateQueries({ queryKey: [ME_KEY, "match"] });
}

export function useApply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { jobSlug: string; message: string }) => applyTo(api, v.jobSlug, v.message),
    onSuccess: () => qc.invalidateQueries({ queryKey: meKeys.applications }),
  });
}

export function useWithdraw() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) => withdrawApplication(api, applicationId),
    onSuccess: () => qc.invalidateQueries({ queryKey: meKeys.applications }),
  });
}

export function useToggleSave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { slug: string; saved: boolean }) => {
      if (v.saved) await unsaveJob(api, v.slug);
      else await saveJob(api, v.slug);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: meKeys.saved }),
  });
}

export function useRegisterInterest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { courseSlug: string; message: string }) => registerInterest(api, v.courseSlug, v.message),
    onSuccess: () => qc.invalidateQueries({ queryKey: meKeys.interests }),
  });
}

export function useWithdrawInterest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (interestId: string) => withdrawInterest(api, interestId),
    onSuccess: () => qc.invalidateQueries({ queryKey: meKeys.interests }),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileUpdate) => updateProfile(api, body),
    onSuccess: (profile) => {
      qc.setQueryData(meKeys.profile, profile);
      void qc.invalidateQueries({ queryKey: meKeys.matches });
      void qc.invalidateQueries({ queryKey: [ME_KEY, "match"] });
    },
  });
}

export function useAddSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BulkBody) => addSkillsBulk(api, body),
    onSuccess: (profile) => {
      qc.setQueryData(meKeys.profile, profile);
      skillsChanged(qc);
    },
  });
}

export function useRemoveSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => removeSkill(api, slug),
    onSuccess: (profile) => {
      qc.setQueryData(meKeys.profile, profile);
      skillsChanged(qc);
    },
  });
}
