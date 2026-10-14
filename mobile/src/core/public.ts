/**
 * What a visitor can read without signing in: vacancies, courses and standards, and the search over
 * them. Plain functions over the typed client, so the rules (a page is 20 rows, a failure keeps the
 * server's sentence, a 404 stays a 404) are tested in Node and the screens stay thin.
 *
 * **Every query built from these is keyed `["public", ...]`** (`src/lib/queries.ts`), which is what
 * lets `persist.ts` keep them for offline reading and nothing else. Nothing in this file may take or
 * return anything about a person.
 *
 * No React Native import: this file is tested in Node.
 */

import type { Api } from "./api";
import { ApiError, readDetail } from "./errors";

export const PAGE_SIZE = 20;

type Outcome<T> = { data?: T; error?: unknown; response: { status: number } };

/**
 * The data, or an `ApiError` carrying the status and the server's own sentence. The status is read
 * before the check: several of these routes document no error body, so openapi-fetch narrows the
 * failure branch to `never` (the web's `useOperatorDashboard`).
 */
export function unwrap<T>(result: Outcome<T>): T {
  const status = result.response.status;
  const failure: unknown = result.error;
  if (failure !== undefined && failure !== null) throw new ApiError(status, readDetail(failure));
  if (result.data === undefined) throw new ApiError(status, null);
  return result.data;
}

export type JobFilter = { q?: string; employmentType?: string; state?: string; skill?: string };
export type CourseFilter = { q?: string; mode?: string; language?: string; skill?: string };
type Employment = "full_time" | "part_time" | "contract" | "apprenticeship" | "gig";

const trimmed = (q?: string) => (q ?? "").trim();

export async function listJobs(api: Api, filter: JobFilter, offset = 0) {
  const q = trimmed(filter.q);
  return unwrap(
    await api.GET("/jobs", {
      params: {
        query: {
          limit: PAGE_SIZE,
          offset,
          ...(q ? { q } : {}),
          ...(filter.employmentType ? { employment_type: filter.employmentType as Employment } : {}),
          ...(filter.state ? { location_state: filter.state } : {}),
          ...(filter.skill ? { skill: filter.skill } : {}),
        },
      },
    }),
  );
}

export async function getJob(api: Api, slug: string) {
  return unwrap(await api.GET("/jobs/{slug}", { params: { path: { slug } } }));
}

export async function listCourses(api: Api, filter: CourseFilter, offset = 0) {
  const q = trimmed(filter.q);
  return unwrap(
    await api.GET("/courses", {
      params: {
        query: {
          limit: PAGE_SIZE,
          offset,
          ...(q ? { q } : {}),
          ...(filter.mode ? { mode: filter.mode as "online" | "offline" | "hybrid" } : {}),
          ...(filter.language ? { language: filter.language as "en" | "hi" | "both" } : {}),
          ...(filter.skill ? { skill: filter.skill } : {}),
        },
      },
    }),
  );
}

export async function getCourse(api: Api, slug: string) {
  return unwrap(await api.GET("/courses/{slug}", { params: { path: { slug } } }));
}

export async function listSkills(api: Api, skillType: string | undefined, offset = 0) {
  return unwrap(
    await api.GET("/skills", {
      params: {
        query: {
          limit: PAGE_SIZE,
          offset,
          ...(skillType ? { skill_type: skillType as "technical" | "core" | "generic" } : {}),
        },
      },
    }),
  );
}

/** Capped by the server at 50 and not paged: a search is for finding one standard, not reading all. */
export async function searchSkills(api: Api, q: string, limit = 50) {
  return unwrap(await api.GET("/skills/search", { params: { query: { q: trimmed(q), limit } } }));
}

export async function searchRoles(api: Api, q: string, limit = 5) {
  return unwrap(await api.GET("/roles/search", { params: { query: { q: trimmed(q), limit } } }));
}

export async function getSkill(api: Api, slug: string) {
  return unwrap(await api.GET("/skills/{slug}", { params: { path: { slug } } }));
}

export async function skillJobs(api: Api, slug: string, limit = 5) {
  return unwrap(
    await api.GET("/skills/{slug}/jobs", { params: { path: { slug }, query: { limit } } }),
  );
}

export async function skillCourses(api: Api, slug: string, limit = 5) {
  return unwrap(
    await api.GET("/skills/{slug}/courses", { params: { path: { slug }, query: { limit } } }),
  );
}

/** The next `offset` for an infinite list, or `undefined` once everything has been fetched. */
export function nextOffset(page: { offset: number; limit: number; total: number }): number | undefined {
  const next = page.offset + page.limit;
  return next < page.total ? next : undefined;
}
