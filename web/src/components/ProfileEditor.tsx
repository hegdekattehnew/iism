"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Button, ButtonLink } from "@/components/ui";
import { api } from "@/lib/api";
import { useIsSignedIn } from "@/lib/auth";

const EDUCATION = [
  "none", "primary", "secondary", "higher_secondary",
  "iti", "diploma", "graduate", "postgraduate",
] as const;

type Education = (typeof EDUCATION)[number];

export function ProfileEditor() {
  const t = useTranslations("profilePage");
  const ts = useTranslations("skillsPage");
  const isHi = useLocale() === "hi";
  const qc = useQueryClient();

  const signedIn = useIsSignedIn();

  const profile = useQuery({
    queryKey: ["profile"],
    enabled: signedIn === true,
    queryFn: async () => {
      const { data } = await api.GET("/me/profile");
      return data ?? null;
    },
  });

  // The form is uncontrolled and keyed on the loaded profile. That removes the
  // "sync server data into state" effect entirely, along with the class of bug
  // where a fetch overwrites what the user is halfway through typing.
  const save = useMutation({
    mutationFn: async (form: FormData) => {
      const str = (k: string) => (form.get(k) as string)?.trim() || null;
      const { data } = await api.PUT("/me/profile", {
        body: {
          headline: str("headline"),
          location_state: str("location_state"),
          location_district: str("location_district"),
          years_experience: Number(form.get("years_experience")) || 0,
          education_level: (str("education_level") ?? null) as Education | null,
        },
      });
      return data ?? null;
    },
    onSuccess: (data) => qc.setQueryData(["profile"], data),
  });

  // --- skill search + add
  const [query, setQuery] = useState("");
  const [proficiency, setProficiency] = useState(3);
  const deferred = useDeferredValue(query.trim());

  const search = useQuery({
    queryKey: ["profile-skill-search", deferred],
    enabled: deferred.length > 0,
    queryFn: async () => {
      const { data } = await api.GET("/skills/search", {
        params: { query: { q: deferred, limit: 8 } },
      });
      return data ?? [];
    },
  });

  const addSkill = useMutation({
    mutationFn: async (slug: string) => {
      const { data } = await api.POST("/me/profile/skills", {
        body: { skill_slug: slug, proficiency },
      });
      return data ?? null;
    },
    onSuccess: (data) => {
      qc.setQueryData(["profile"], data);
      setQuery("");
    },
  });

  const removeSkill = useMutation({
    mutationFn: async (slug: string) => {
      const { data } = await api.DELETE("/me/profile/skills/{skill_slug}", {
        params: { path: { skill_slug: slug } },
      });
      return data ?? null;
    },
    onSuccess: (data) => qc.setQueryData(["profile"], data),
  });

  if (!signedIn) {
    return (
      <div className="rounded-xl border border-border-token bg-surface p-8 text-center">
        <p className="text-sm text-muted">{t("signInPrompt")}</p>
        <div className="mt-4">
          <ButtonLink href="/signin">{t("goToSignIn")}</ButtonLink>
        </div>
      </div>
    );
  }

  const held = new Set((profile.data?.skills ?? []).map((s) => s.skill.slug));

  return (
    <div className="space-y-8">
      {/* ---------------------------------------------------------- details */}
      <section className="rounded-xl border border-border-token bg-surface p-6">
        <h2 className="text-base font-semibold">{t("detailsTitle")}</h2>
        <form
          key={profile.data?.id ?? "loading"}
          className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate(new FormData(e.currentTarget));
          }}
        >
          <label className="sm:col-span-2">
            <span className="text-sm font-medium">{t("headline")}</span>
            <input
              name="headline"
              defaultValue={profile.data?.headline ?? ""}
              placeholder={t("headlinePlaceholder")}
              maxLength={160}
              className="mt-1.5 w-full rounded-lg border border-border-token bg-background px-3 py-2.5 text-sm"
            />
          </label>
          <label>
            <span className="text-sm font-medium">{t("state")}</span>
            <input
              name="location_state"
              defaultValue={profile.data?.location_state ?? ""}
              className="mt-1.5 w-full rounded-lg border border-border-token bg-background px-3 py-2.5 text-sm"
            />
          </label>
          <label>
            <span className="text-sm font-medium">{t("district")}</span>
            <input
              name="location_district"
              defaultValue={profile.data?.location_district ?? ""}
              className="mt-1.5 w-full rounded-lg border border-border-token bg-background px-3 py-2.5 text-sm"
            />
          </label>
          <label>
            <span className="text-sm font-medium">{t("experience")}</span>
            <input
              type="number"
              name="years_experience"
              min={0}
              max={60}
              defaultValue={profile.data?.years_experience ?? 0}
              className="mt-1.5 w-full rounded-lg border border-border-token bg-background px-3 py-2.5 text-sm"
            />
          </label>
          <label>
            <span className="text-sm font-medium">{t("education")}</span>
            <select
              name="education_level"
              defaultValue={profile.data?.education_level ?? ""}
              className="mt-1.5 w-full rounded-lg border border-border-token bg-background px-3 py-2.5 text-sm"
            >
              <option value="">—</option>
              {EDUCATION.map((e) => (
                <option key={e} value={e}>
                  {t(`educationLevel.${e}`)}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? t("saving") : t("save")}
            </Button>
            {save.isSuccess && (
              <span className="text-sm text-emerald-600 dark:text-emerald-400">
                {t("saved")}
              </span>
            )}
          </div>
        </form>
      </section>

      {/* ----------------------------------------------------------- skills */}
      <section className="rounded-xl border border-border-token bg-surface p-6">
        <h2 className="text-base font-semibold">{t("skillsTitle")}</h2>
        <p className="mt-1 text-sm text-muted">{t("skillsSubtitle")}</p>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            aria-label={t("searchPlaceholder")}
            className="w-full flex-1 rounded-lg border border-border-token bg-background px-4 py-2.5 text-sm"
          />
          <label className="flex items-center gap-2 text-sm">
            <span className="whitespace-nowrap text-muted">
              {t("proficiencyLabel")}
            </span>
            <select
              value={proficiency}
              onChange={(e) => setProficiency(Number(e.target.value))}
              className="rounded-lg border border-border-token bg-background px-2 py-2.5 text-sm"
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>

        {deferred && (
          <ul className="mt-3 space-y-1.5">
            {(search.data ?? []).map((s) => (
              <li
                key={s.slug}
                className="flex items-center gap-3 rounded-lg border border-border-token bg-background px-3 py-2"
              >
                <span className="flex-1 text-sm">
                  {isHi && s.name_hi ? s.name_hi : s.name_en}
                  {s.matched_on && s.match_kind === "alias" && (
                    <span className="ml-2 text-xs text-brand">
                      {ts("matchedVia", { term: s.matched_on })}
                    </span>
                  )}
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={held.has(s.slug) || addSkill.isPending}
                  onClick={() => addSkill.mutate(s.slug)}
                >
                  {t("add")}
                </Button>
              </li>
            ))}
          </ul>
        )}

        <ul className="mt-5 space-y-2">
          {(profile.data?.skills ?? []).map((s) => (
            <li
              key={s.skill.slug}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-border-token bg-background px-3 py-2.5"
            >
              <span className="text-sm font-medium">
                {isHi && s.skill.name_hi ? s.skill.name_hi : s.skill.name_en}
              </span>
              <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[11px] text-muted">
                {t("proficiency", { n: s.proficiency })}
              </span>
              <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[11px] font-medium text-brand">
                {t(`source.${s.source}`)}
              </span>
              <button
                type="button"
                onClick={() => removeSkill.mutate(s.skill.slug)}
                className="ml-auto text-xs text-muted hover:text-rose-600 hover:underline"
              >
                {t("remove")}
              </button>
            </li>
          ))}
        </ul>

        {(profile.data?.skills ?? []).length === 0 && (
          <p className="mt-5 text-sm text-muted">{t("noSkills")}</p>
        )}

        <p className="mt-5 border-t border-border-token pt-4 text-xs text-muted">
          {t("sourceNote")}
        </p>
      </section>
    </div>
  );
}
