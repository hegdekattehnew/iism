import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import {
  getCourse,
  getJob,
  getSkill,
  listCourses,
  listJobs,
  listSkills,
  nextOffset,
  PAGE_SIZE,
  searchRoles,
  searchSkills,
  skillCourses,
  skillJobs,
  type CourseFilter,
  type JobFilter,
} from "../core/public";
import { PUBLIC_KEY } from "../core/persist";
import { api, useLocale } from "../runtime";

/**
 * The queries a visitor's screens use. **Every key starts with `"public"` and then the language**:
 *
 * - `"public"` is what lets `core/persist.ts` keep them for offline reading and nothing else;
 * - the language is in the key because the API answers in the language it is asked for
 *   (`Accept-Language`, ADR-041), so a Hindi list must never be served from an English cache.
 *
 * A query about a person does not belong in this file.
 */

export type SkillBrowse = { q?: string; skillType?: string };

export function useJobs(filter: JobFilter) {
  const locale = useLocale();
  return useInfiniteQuery({
    queryKey: [PUBLIC_KEY, locale, "jobs", filter],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => listJobs(api, filter, pageParam),
    getNextPageParam: nextOffset,
  });
}

export function useCourses(filter: CourseFilter) {
  const locale = useLocale();
  return useInfiniteQuery({
    queryKey: [PUBLIC_KEY, locale, "courses", filter],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => listCourses(api, filter, pageParam),
    getNextPageParam: nextOffset,
  });
}

/**
 * Standards: a page of the catalogue, or, once there is a search term, the server's best matches.
 * A search is not paged (it is capped at 50 by the server), so it answers in the same page shape
 * with nothing after it, and the list component does not need to know the difference.
 */
export function useSkills({ q, skillType }: SkillBrowse) {
  const locale = useLocale();
  const term = (q ?? "").trim();
  return useInfiniteQuery({
    queryKey: [PUBLIC_KEY, locale, "skills", { q: term, skillType }],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      if (term) {
        const hits = await searchSkills(api, term);
        return { items: hits, total: hits.length, limit: hits.length || PAGE_SIZE, offset: 0 };
      }
      return listSkills(api, skillType, pageParam);
    },
    getNextPageParam: nextOffset,
  });
}

export const useJob = (slug: string) => {
  const locale = useLocale();
  return useQuery({ queryKey: [PUBLIC_KEY, locale, "job", slug], queryFn: () => getJob(api, slug) });
};

export const useCourse = (slug: string) => {
  const locale = useLocale();
  return useQuery({
    queryKey: [PUBLIC_KEY, locale, "course", slug],
    queryFn: () => getCourse(api, slug),
  });
};

export const useSkill = (slug: string) => {
  const locale = useLocale();
  return useQuery({
    queryKey: [PUBLIC_KEY, locale, "skill", slug],
    queryFn: () => getSkill(api, slug),
  });
};

export const useSkillJobs = (slug: string) => {
  const locale = useLocale();
  return useQuery({
    queryKey: [PUBLIC_KEY, locale, "skill-jobs", slug],
    queryFn: () => skillJobs(api, slug),
  });
};

export const useSkillCourses = (slug: string) => {
  const locale = useLocale();
  return useQuery({
    queryKey: [PUBLIC_KEY, locale, "skill-courses", slug],
    queryFn: () => skillCourses(api, slug),
  });
};

/** The three bands of the search screen. Nothing is asked until there is something to ask. */
export function useSearch(q: string) {
  const locale = useLocale();
  const term = q.trim();
  const enabled = term.length > 0;
  const jobs = useQuery({
    queryKey: [PUBLIC_KEY, locale, "search", "jobs", term],
    enabled,
    queryFn: () => listJobs(api, { q: term }).then((page) => ({ ...page, items: page.items.slice(0, 5) })),
  });
  const roles = useQuery({
    queryKey: [PUBLIC_KEY, locale, "search", "roles", term],
    enabled,
    queryFn: () => searchRoles(api, term),
  });
  const standards = useQuery({
    queryKey: [PUBLIC_KEY, locale, "search", "standards", term],
    enabled,
    queryFn: () => searchSkills(api, term),
  });
  return { jobs, roles, standards };
}
