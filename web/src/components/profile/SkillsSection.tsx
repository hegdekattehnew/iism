"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Select } from "@/components/profile/fields";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { type Profile, useProfileMutations } from "@/lib/profile";

export function SkillsSection({ profile }: { profile: Profile | null }) {
  const t = useTranslations("profilePage");
  const ts = useTranslations("skillsPage");
  const isHi = useLocale() === "hi";
  const { addSkill, removeSkill } = useProfileMutations();

  const [query, setQuery] = useState("");
  const [proficiency, setProficiency] = useState(3);
  const deferred = useDeferredValue(query.trim());

  const search = useQuery({
    queryKey: ["profile-skill-search", deferred],
    enabled: deferred.length > 0,
    queryFn: async () =>
      (await api.GET("/skills/search", { params: { query: { q: deferred, limit: 8 } } }))
        .data ?? [],
  });

  const held = new Set((profile?.skills ?? []).map((s) => s.skill.slug));

  return (
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
          <span className="whitespace-nowrap text-muted">{t("proficiencyLabel")}</span>
          <Select
            value={proficiency}
            onChange={(e) => setProficiency(Number(e.target.value))}
            className="mt-0 w-auto"
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </Select>
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
                onClick={() => addSkill.mutate({ skill_slug: s.slug, proficiency })}
              >
                {t("add")}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <ul className="mt-5 space-y-2">
        {(profile?.skills ?? []).map((s) => (
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

      {(profile?.skills ?? []).length === 0 && (
        <p className="mt-5 text-sm text-muted">{t("noSkills")}</p>
      )}
      <p className="mt-5 border-t border-border-token pt-4 text-xs text-muted">
        {t("sourceNote")}
      </p>
    </section>
  );
}
