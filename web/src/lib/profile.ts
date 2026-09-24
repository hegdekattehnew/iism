"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { ApiError, readDetail } from "@/lib/http";
import type { paths } from "@/lib/api-schema";

export type Collection =
  | "experiences"
  | "educations"
  | "certifications"
  | "languages"
  | "preferred_roles"
  | "preferred_locations";

// Derived from the generated schema rather than the client's call signature,
// which is not generic-instantiable.
export type Profile =
  paths["/me/profile"]["get"]["responses"][200]["content"]["application/json"];

export const GENDERS = ["female", "male", "other", "prefer_not_to_say"] as const;
export const NOTICE = [
  "immediate",
  "within_15_days",
  "within_30_days",
  "over_30_days",
] as const;
export const LANG_PROFICIENCY = [
  "basic",
  "conversational",
  "fluent",
  "native",
] as const;
export const EDUCATION_LEVELS = [
  "none",
  "primary",
  "secondary",
  "higher_secondary",
  "iti",
  "diploma",
  "graduate",
  "postgraduate",
] as const;
export const EMPLOYMENT_TYPES = [
  "full_time",
  "part_time",
  "contract",
  "apprenticeship",
] as const;

export function useProfile(enabled = true) {
  return useQuery({
    queryKey: ["profile"],
    enabled,
    queryFn: async () => (await api.GET("/me/profile")).data ?? null,
  });
}

/**
 * Every mutation returns the whole profile, so the cache is replaced from the
 * server response rather than invalidated. One round trip, and the completeness
 * meter can never drift from the data it describes.
 */
export function useProfileMutations() {
  const qc = useQueryClient();
  const write = (data: unknown) => qc.setQueryData(["profile"], data);

  const saveDetails = useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      const { data, error, response } = await api.PUT("/me/profile", {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        body: body as any,
      });
      if (error) throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: write,
  });

  const addEntry = useMutation({
    mutationFn: async (v: { collection: Collection; body: Record<string, unknown> }) => {
      const { data, error, response } = await api.POST("/me/profile/{collection}", {
        params: { path: { collection: v.collection } },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        body: v.body as any,
      });
      if (error)
        // `ApiError`, so the screen can say which field the server
        // refused instead of "Could not save. Please check the fields."
        throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: write,
  });

  const updateEntry = useMutation({
    mutationFn: async (v: {
      collection: Collection;
      id: string;
      body: Record<string, unknown>;
    }) => {
      const { data, error, response } = await api.PUT(
        "/me/profile/{collection}/{entry_id}",
        {
          params: { path: { collection: v.collection, entry_id: v.id } },
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          body: v.body as any,
        },
      );
      if (error)
        // `ApiError`, so the screen can say which field the server
        // refused instead of "Could not save. Please check the fields."
        throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: write,
  });

  const removeEntry = useMutation({
    mutationFn: async (v: { collection: Collection; id: string }) => {
      const { data, error, response } = await api.DELETE(
        "/me/profile/{collection}/{entry_id}",
        { params: { path: { collection: v.collection, entry_id: v.id } } },
      );
      if (error) throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: write,
  });

  const addSkill = useMutation({
    mutationFn: async (v: { skill_slug: string; proficiency: number }) => {
      const { data, error, response } = await api.POST("/me/profile/skills", { body: v });
      if (error) throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: write,
  });

  // Several standards in one request: the ones ticked from a suggested role.
  // One decision, one round trip, and all-or-nothing on the server.
  const addSkillsBulk = useMutation({
    mutationFn: async (v: {
      items: { skill_slug: string; proficiency: number }[];
      preferred_role_title?: string | null;
    }) => {
      const { data, error, response } = await api.POST("/me/profile/skills/bulk", {
        body: v,
      });
      if (error)
        // `ApiError`, so the screen can say which field the server
        // refused instead of "Could not save. Please check the fields."
        throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: write,
  });

  const removeSkill = useMutation({
    mutationFn: async (slug: string) => {
      const { data, error, response } = await api.DELETE(
        "/me/profile/skills/{skill_slug}",
        { params: { path: { skill_slug: slug } } },
      );
      if (error) throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: write,
  });

  const finishOnboarding = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.POST(
        "/me/profile/onboarding/complete",
        {},
      );
      // See `Notices.tsx`: the status is read before the narrowing.
      const status = response.status;
      if (error) throw new ApiError(status, readDetail(error));
      return data;
    },
    onSuccess: write,
  });

  return {
    saveDetails,
    addEntry,
    updateEntry,
    removeEntry,
    addSkill,
    addSkillsBulk,
    removeSkill,
    finishOnboarding,
  };
}
