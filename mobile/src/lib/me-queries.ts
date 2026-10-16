import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import {
  confirmConsent,
  deleteAccount,
  exportFile,
  fetchConsent,
  fetchDeletionPreview,
  fetchExport,
  withdrawConsent,
} from "../core/account";
import { ApiError, readDetail } from "../core/errors";
import { listMyMessages, sendMessage, type MessageDraft } from "../core/grievance";
import {
  addEntry,
  addSkillsBulk,
  applyTo,
  getApplicationGap,
  getCareers,
  getMatch,
  getProfile,
  listApplications,
  listInterests,
  listMatches,
  listNotices,
  markAllNoticesRead,
  markNoticeRead,
  listSaved,
  registerInterest,
  removeEntry,
  removeSkill,
  roleStandards,
  saveJob,
  searchRoleHits,
  unreadCount,
  unsaveJob,
  updateEntry,
  updateProfile,
  withdrawApplication,
  withdrawInterest,
  type ProfileUpdate,
} from "../core/me";
import type { Collection } from "../core/profile-sections";
import { ME_KEY, meKeys } from "../core/me-keys";
import { NOTICE_PAGE_SIZE, nextCursor } from "../core/notices";
import { reportListing, type Reason, type Target } from "../core/report";
import type { BulkBody } from "../core/role-picker";
import { PRIVACY_NOTICE_VERSION } from "../core/sign-in";
import { api, useCourseBudget, useSignedIn } from "../runtime";

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

/** One match. The course budget is part of the key: another budget is another order of courses. */
export function useMatch(slug: string) {
  const { enabled } = useSeeker();
  const budget = useCourseBudget();
  return useQuery({
    queryKey: meKeys.match(slug, budget),
    enabled,
    queryFn: () => getMatch(api, slug, budget),
  });
}

/** "Why not me": what one of the person's own applications was missing, computed now. */
export function useApplicationGap(applicationId: string) {
  const { enabled } = useSeeker();
  const budget = useCourseBudget();
  return useQuery({
    queryKey: meKeys.gap(applicationId, budget),
    enabled: enabled && applicationId !== "",
    queryFn: () => getApplicationGap(api, applicationId, budget),
  });
}

/** The roles that build on the person's own. `role` is their choice; null lets the server guess once. */
export function useCareers(role: string | null) {
  const { enabled } = useSeeker();
  const budget = useCourseBudget();
  return useQuery({
    queryKey: meKeys.careers(role, budget),
    enabled,
    queryFn: () => getCareers(api, role, budget),
  });
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

/**
 * A section entry changes what the profile says, and some of it (a preferred role or place) what
 * the matches show, so a write refreshes the lot, as a skill does. The server answers with the whole
 * profile, which replaces the cached one.
 */
function entryWritten(qc: QueryClient, profile: unknown) {
  qc.setQueryData(meKeys.profile, profile);
  void qc.invalidateQueries({ queryKey: meKeys.matches });
  void qc.invalidateQueries({ queryKey: [ME_KEY, "match"] });
  void qc.invalidateQueries({ queryKey: [ME_KEY, "careers"] });
}

export function useAddEntry(collection: Collection) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => addEntry(api, collection, body),
    onSuccess: (profile) => entryWritten(qc, profile),
  });
}

export function useUpdateEntry(collection: Collection) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; body: Record<string, unknown> }) => updateEntry(api, collection, v.id, v.body),
    onSuccess: (profile) => entryWritten(qc, profile),
  });
}

export function useRemoveEntry(collection: Collection) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => removeEntry(api, collection, id),
    onSuccess: (profile) => entryWritten(qc, profile),
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

// ---------------------------------------------------------------- notices

/** Every notice, newest first, a page at a time; the cursor is the last one's time **and** id. */
export function useNoticePages() {
  const { enabled } = useSeeker();
  return useInfiniteQuery({
    queryKey: meKeys.notices,
    enabled,
    initialPageParam: null as { before: string; before_id: string } | null,
    queryFn: ({ pageParam }) => listNotices(api, pageParam, NOTICE_PAGE_SIZE),
    getNextPageParam: (last) => nextCursor(last),
  });
}

/** How often the unread count is asked for while the app is in front. */
export const UNREAD_POLL_MS = 60_000;

/** What the Me tab's badge shows: one indexed count, cheap enough to ask on every launch. */
export function useUnreadCount() {
  const { enabled } = useSeeker();
  return useQuery({
    queryKey: meKeys.unread,
    enabled,
    queryFn: () => unreadCount(api),
    // The tab is mounted for the whole session, so without these the number would be the one read
    // at launch. A minute is cheap (a count, no body), and it does not run while the app is in the
    // background: coming back to the foreground refetches at once (see the root layout).
    refetchInterval: UNREAD_POLL_MS,
    refetchOnWindowFocus: true,
  });
}

function noticesChanged(qc: QueryClient) {
  void qc.invalidateQueries({ queryKey: meKeys.notices });
  void qc.invalidateQueries({ queryKey: meKeys.unread });
}

export function useReadOne() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => markNoticeRead(api, id),
    onSuccess: () => noticesChanged(qc),
  });
}

export function useReadAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => markAllNoticesRead(api),
    onSuccess: () => noticesChanged(qc),
  });
}

// ------------------------------------------------------- messages and reports

/** What the signed-in person has sent the team, and where each stands. */
export function useMyMessages() {
  const { enabled } = useSeeker();
  return useQuery({ queryKey: meKeys.messages, enabled, queryFn: () => listMyMessages(api) });
}

/** A message to the team. Open to a signed-out visitor too, so it is not gated on an account. */
export function useSendMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (draft: MessageDraft) => sendMessage(api, draft),
    onSuccess: () => qc.invalidateQueries({ queryKey: meKeys.messages }),
  });
}

export function useReportListing(target: Target, slug: string) {
  return useMutation({
    mutationFn: (v: { reason: Reason; detail: string }) =>
      reportListing(api, target, slug, v.reason, v.detail),
  });
}

// ---------------------------------------------------------------- the account

/** What deleting the account would take with it. Asked only once the person says they might. */
export function useDeletionPreview(wanted: boolean) {
  const { enabled } = useSeeker();
  return useQuery({
    queryKey: meKeys.deletion,
    enabled: enabled && wanted,
    // A preview is a fact about now: never served from a stale cache to somebody about to act on it.
    staleTime: 0,
    gcTime: 0,
    queryFn: () => fetchDeletionPreview(api),
  });
}

/** The person's data as text for the share sheet, with the file name it would be saved under. */
export function useExportData() {
  return useMutation({
    mutationFn: async (today: string) => exportFile(await fetchExport(api), today),
  });
}

export function useDeleteAccount() {
  return useMutation({ mutationFn: () => deleteAccount(api) });
}

/** Where the person stands on consent, and what withdrawing would take back. */
export function useConsent() {
  const { signedIn } = useAccount();
  return useQuery({
    queryKey: meKeys.consent,
    enabled: signedIn,
    // A preview of what a withdrawal would end is a fact about now: never a stale cache.
    staleTime: 0,
    queryFn: () => fetchConsent(api),
  });
}

/** What changes with consent: the account (`consent_*`), the preview, and every disclosure it ends. */
function consentChanged(qc: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: meKeys.account }),
    qc.invalidateQueries({ queryKey: meKeys.consent }),
    qc.invalidateQueries({ queryKey: meKeys.applications }),
    qc.invalidateQueries({ queryKey: meKeys.interests }),
  ]);
}

/** Withdraw consent and keep the account: a pause, not an erasure. */
export function useWithdrawConsent() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => withdrawConsent(api), onSuccess: () => consentChanged(qc) });
}

/** Confirm the notice in force, with this build's own version. */
export function useConfirmConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => confirmConsent(api, PRIVACY_NOTICE_VERSION),
    onSuccess: () => consentChanged(qc),
  });
}
