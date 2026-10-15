/**
 * Everything the signed-in candidate reads and writes: the profile and its skills, matches,
 * applications, saved vacancies and course interests. Plain functions over the typed client, so
 * "a failure keeps the server's sentence" is tested in Node and the screens stay thin.
 *
 * **Every query built from these is keyed `["me", ...]`** (`me-keys.ts`): never persisted, and
 * removed when the person signs out. Nothing here is cached by the public allow-list.
 *
 * No React Native import: this file is tested in Node.
 */

import type { components } from "../api/schema";
import type { Api } from "./api";
import { ApiError, readDetail } from "./errors";
import { budgetQuery } from "./course-budget";
import { unwrap } from "./public";
import type { Collection } from "./profile-sections";

export type Profile = components["schemas"]["CandidateProfileFull"];
export type ProfileUpdate = components["schemas"]["CandidateProfileUpdateFull"];
export type RoleHit = components["schemas"]["RoleHit"];

/** A write that answers with no body (a 204) or one we do not read: ok, or an `ApiError`. */
function expectOk(result: { error?: unknown; response: { status: number } }): void {
  const failure: unknown = result.error;
  if (failure !== undefined && failure !== null) {
    throw new ApiError(result.response.status, readDetail(failure));
  }
}

// ------------------------------------------------------------------ profile

export async function getProfile(api: Api) {
  return unwrap(await api.GET("/me/profile"));
}

export async function updateProfile(api: Api, body: ProfileUpdate) {
  return unwrap(await api.PUT("/me/profile", { body }));
}

export async function addSkillsBulk(
  api: Api,
  body: { items: { skill_slug: string; proficiency: number }[]; preferred_role_title: string | null },
) {
  return unwrap(await api.POST("/me/profile/skills/bulk", { body }));
}

export async function removeSkill(api: Api, slug: string) {
  return unwrap(
    await api.DELETE("/me/profile/skills/{skill_slug}", { params: { path: { skill_slug: slug } } }),
  );
}

// ------------------------------------------------------ profile sections

/**
 * The six repeating sections share three routes that take an **untyped body** (so the 422 for a bad
 * one is a list, which `readDetail` joins), and each answers with the whole profile.
 */
export async function addEntry(api: Api, collection: Collection, body: Record<string, unknown>) {
  return unwrap(await api.POST("/me/profile/{collection}", { params: { path: { collection } }, body }));
}

export async function updateEntry(api: Api, collection: Collection, id: string, body: Record<string, unknown>) {
  return unwrap(
    await api.PUT("/me/profile/{collection}/{entry_id}", {
      params: { path: { collection, entry_id: id } },
      body,
    }),
  );
}

export async function removeEntry(api: Api, collection: Collection, id: string) {
  return unwrap(
    await api.DELETE("/me/profile/{collection}/{entry_id}", { params: { path: { collection, entry_id: id } } }),
  );
}

export async function searchRoleHits(api: Api, q: string, limit = 8) {
  return unwrap(await api.GET("/roles/search", { params: { query: { q: q.trim(), limit } } }));
}

export async function roleStandards(api: Api, slug: string) {
  return unwrap(await api.GET("/roles/{slug}/standards", { params: { path: { slug } } }));
}

// ------------------------------------------------------------------ matches

export const MATCH_LIMIT = 50;

export async function listMatches(api: Api) {
  return unwrap(await api.GET("/me/matches", { params: { query: { limit: MATCH_LIMIT } } }));
}

export async function getMatch(api: Api, slug: string, budget: number | null = null) {
  return unwrap(
    await api.GET("/me/matches/{slug}", { params: { path: { slug }, query: budgetQuery(budget) } }),
  );
}

// ------------------------------------------------------- why not me, careers

/** What one of the person's own applications was missing, and the courses that teach it. */
export async function getApplicationGap(api: Api, applicationId: string, budget: number | null = null) {
  return unwrap(
    await api.GET("/me/applications/{application_id}/gap", {
      params: { path: { application_id: applicationId }, query: budgetQuery(budget) },
    }),
  );
}

/** The roles that build on the person's own: from `role` if they chose one, else a flagged guess. */
export async function getCareers(api: Api, role: string | null, budget: number | null = null) {
  return unwrap(
    await api.GET("/me/careers", { params: { query: { ...(role ? { role } : {}), ...budgetQuery(budget) } } }),
  );
}

// ------------------------------------------------------------- applications

export async function listApplications(api: Api) {
  return unwrap(await api.GET("/me/applications"));
}

export async function applyTo(api: Api, jobSlug: string, message: string) {
  const note = message.trim();
  return unwrap(
    await api.POST("/me/applications", { body: { job_slug: jobSlug, message: note ? note : null } }),
  );
}

export async function withdrawApplication(api: Api, id: string) {
  return unwrap(
    await api.POST("/me/applications/{application_id}/withdraw", {
      params: { path: { application_id: id } },
    }),
  );
}

export async function listSaved(api: Api) {
  return unwrap(await api.GET("/me/saved-jobs"));
}

export async function saveJob(api: Api, slug: string) {
  return unwrap(await api.POST("/me/saved-jobs", { body: { job_slug: slug } }));
}

export async function unsaveJob(api: Api, slug: string) {
  expectOk(await api.DELETE("/me/saved-jobs/{job_slug}", { params: { path: { job_slug: slug } } }));
}

// ---------------------------------------------------------------- interests

export async function listInterests(api: Api) {
  return unwrap(await api.GET("/me/course-interests"));
}

export async function registerInterest(api: Api, courseSlug: string, message: string) {
  const note = message.trim();
  return unwrap(
    await api.POST("/me/course-interests", {
      body: { course_slug: courseSlug, message: note ? note : null },
    }),
  );
}

export async function withdrawInterest(api: Api, id: string) {
  return unwrap(
    await api.POST("/me/course-interests/{interest_id}/withdraw", {
      params: { path: { interest_id: id } },
    }),
  );
}

// ------------------------------------------------------------------ notices

export type NoticeCursor = { before: string; before_id: string };

export async function listNotices(api: Api, cursor: NoticeCursor | null, limit = 30) {
  return unwrap(
    await api.GET("/me/notifications", { params: { query: { limit, ...(cursor ?? {}) } } }),
  );
}

export async function unreadCount(api: Api): Promise<number> {
  return unwrap(await api.GET("/me/notifications/unread-count")).unread ?? 0;
}

export async function markNoticeRead(api: Api, id: string): Promise<void> {
  expectOk(
    await api.POST("/me/notifications/{notification_id}/read", {
      params: { path: { notification_id: id } },
    }),
  );
}

export async function markAllNoticesRead(api: Api): Promise<void> {
  expectOk(await api.POST("/me/notifications/read"));
}

// ------------------------------------------------------------------ devices

export async function registerDevice(
  api: Api,
  body: { token: string; platform: "android" | "ios"; locale: string },
): Promise<void> {
  expectOk(await api.POST("/me/devices", { body }));
}

export async function unregisterDevice(api: Api, token: string): Promise<void> {
  expectOk(await api.POST("/me/devices/unregister", { body: { token } }));
}
