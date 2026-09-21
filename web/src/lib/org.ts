"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { paths } from "./api-schema";
import { api } from "./api";

/**
 * The employer workspace's data layer.
 *
 * Deliberately a parallel to `lib/profile.ts` rather than a reuse of it. That
 * module's whole contract is "every mutation returns the entire profile, so the
 * cache is replaced from the response" — which works because all six of its
 * collections hang off one row derived from the JWT. A job has no such implicit
 * parent: the organisation is named in the path and granted by membership, and
 * there are many jobs rather than one aggregate.
 */

export type OrgJob =
  paths["/org/{org_slug}/jobs"]["get"]["responses"][200]["content"]["application/json"][number];

export type Membership = NonNullable<
  paths["/auth/me"]["get"]["responses"][200]["content"]["application/json"]["memberships"]
>[number];

export type JobPayload =
  paths["/org/{org_slug}/jobs"]["post"]["requestBody"]["content"]["application/json"];

/** Every context the signed-in person can act in — one identity, many roles.
 *
 * Two derived lists, because the two callers want different things. The
 * switcher needs every membership so it can offer the job-seeker context
 * alongside the organisations; the workspace needs only the tenants a vacancy
 * can actually be posted from.
 */
export function useMemberships() {
  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, error } = await api.GET("/auth/me");
      if (error || !data) throw new Error("not signed in");
      return data;
    },
    retry: false,
  });

  const memberships = me.data?.memberships ?? [];
  // Every organisation, of either kind. Filtering to employers dropped course
  // providers out of the switcher entirely, so one created through
  // `CreateOrgForm` was navigated into a workspace it could never return to --
  // and the header read "Job seeker" while standing inside it.
  const organisations = memberships.filter(
    (m) => m.tenant.tenant_type !== "personal",
  );
  // Whether this person ever asked to look for work. An organisation-first
  // account has no personal workspace and should not be told it is a job
  // seeker: ADR-038 is about holding many roles, not assuming them.
  const isJobSeeker = memberships.some(
    (m) => m.tenant.tenant_type === "personal",
  );
  return { ...me, memberships, organisations, isJobSeeker };
}

/** The kind of organisation a slug refers to, from data already on the wire. */
export function useOrgType(
  orgSlug: string | null,
): "employer" | "course_provider" | null {
  const { organisations } = useMemberships();
  if (!orgSlug) return null;
  const found = organisations.find((m) => m.tenant.slug === orgSlug);
  return (found?.tenant.tenant_type as "employer" | "course_provider") ?? null;
}

export function useOrgJobs(orgSlug: string | null) {
  return useQuery({
    queryKey: ["org-jobs", orgSlug],
    enabled: orgSlug !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/org/{org_slug}/jobs", {
        params: { path: { org_slug: orgSlug as string } },
      });
      // openapi-fetch resolves rather than throws on a non-2xx, so an
      // unchecked 404 would render as "you have no vacancies" for an
      // organisation the caller simply is not a member of.
      if (error || !data) throw new Error("could not load listings");
      return data;
    },
    retry: false,
  });
}

export function useOrgJobMutations(orgSlug: string) {
  const qc = useQueryClient();
  // Jobs are a list, not one aggregate, so invalidate rather than replace: a
  // publish changes `status` on one row and nothing else on the page.
  const refresh = () =>
    qc.invalidateQueries({ queryKey: ["org-jobs", orgSlug] });

  const create = useMutation({
    mutationFn: async (body: JobPayload) => {
      const { data, error } = await api.POST("/org/{org_slug}/jobs", {
        params: { path: { org_slug: orgSlug } },
        body,
      });
      if (error || !data) throw new Error(String(error ?? "create failed"));
      return data;
    },
    onSuccess: refresh,
  });

  const update = useMutation({
    mutationFn: async ({ slug, body }: { slug: string; body: JobPayload }) => {
      const { data, error } = await api.PUT("/org/{org_slug}/jobs/{slug}", {
        params: { path: { org_slug: orgSlug, slug } },
        body,
      });
      if (error || !data) throw new Error(String(error ?? "update failed"));
      return data;
    },
    onSuccess: refresh,
  });

  const setPublished = useMutation({
    mutationFn: async ({
      slug,
      published,
    }: {
      slug: string;
      published: boolean;
    }) => {
      const path = published
        ? "/org/{org_slug}/jobs/{slug}/publish"
        : "/org/{org_slug}/jobs/{slug}/unpublish";
      const { data, error } = await api.POST(path, {
        params: { path: { org_slug: orgSlug, slug } },
      });
      // The API refuses to publish a job requiring no standards, and that
      // refusal is the message the employer needs to see.
      if (error || !data) throw new Error("publish-refused");
      return data;
    },
    onSuccess: refresh,
  });

  const remove = useMutation({
    mutationFn: async (slug: string) => {
      const { error } = await api.DELETE("/org/{org_slug}/jobs/{slug}", {
        params: { path: { org_slug: orgSlug, slug } },
      });
      if (error) throw new Error("delete failed");
    },
    onSuccess: refresh,
  });

  return { create, update, setPublished, remove };
}

export function useOrgCandidates(
  orgSlug: string | null,
  jobSlug: string | null,
) {
  return useQuery({
    queryKey: ["org-candidates", orgSlug, jobSlug],
    enabled: orgSlug !== null && jobSlug !== null,
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/org/{org_slug}/candidates/{job_slug}",
        {
          params: {
            path: { org_slug: orgSlug as string, job_slug: jobSlug as string },
            query: { limit: 20 },
          },
        },
      );
      if (error || !data) throw new Error("could not rank candidates");
      return data;
    },
    retry: false,
  });
}

export type OrgCourse =
  paths["/org/{org_slug}/courses"]["get"]["responses"][200]["content"]["application/json"][number];

export type CoursePayload =
  paths["/org/{org_slug}/courses"]["post"]["requestBody"]["content"]["application/json"];

export function useOrgCourses(orgSlug: string | null) {
  return useQuery({
    queryKey: ["org-courses", orgSlug],
    enabled: orgSlug !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/org/{org_slug}/courses", {
        params: { path: { org_slug: orgSlug as string } },
      });
      if (error || !data) throw new Error("could not load courses");
      return data;
    },
    retry: false,
  });
}

export function useOrgCourseMutations(orgSlug: string) {
  const qc = useQueryClient();
  const refresh = () =>
    qc.invalidateQueries({ queryKey: ["org-courses", orgSlug] });

  const create = useMutation({
    mutationFn: async (body: CoursePayload) => {
      const { data, error } = await api.POST("/org/{org_slug}/courses", {
        params: { path: { org_slug: orgSlug } },
        body,
      });
      if (error || !data) throw new Error("create failed");
      return data;
    },
    onSuccess: refresh,
  });

  const update = useMutation({
    mutationFn: async ({
      slug,
      body,
    }: {
      slug: string;
      body: CoursePayload;
    }) => {
      const { data, error } = await api.PUT("/org/{org_slug}/courses/{slug}", {
        params: { path: { org_slug: orgSlug, slug } },
        body,
      });
      if (error || !data) throw new Error("update failed");
      return data;
    },
    onSuccess: refresh,
  });

  const setPublished = useMutation({
    mutationFn: async ({
      slug,
      published,
    }: {
      slug: string;
      published: boolean;
    }) => {
      const path = published
        ? "/org/{org_slug}/courses/{slug}/publish"
        : "/org/{org_slug}/courses/{slug}/unpublish";
      const { data, error } = await api.POST(path, {
        params: { path: { org_slug: orgSlug, slug } },
      });
      // The API refuses to publish a course teaching nothing, and that refusal
      // is the message the provider needs to see.
      if (error || !data) throw new Error("publish-refused");
      return data;
    },
    onSuccess: refresh,
  });

  return { create, update, setPublished };
}
