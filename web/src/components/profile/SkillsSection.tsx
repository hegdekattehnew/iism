"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Select } from "@/components/profile/fields";
import { RolePicker } from "@/components/profile/RolePicker";
import { StandardPicker } from "@/components/StandardPicker";
import { type Profile, useProfileMutations } from "@/lib/profile";

/**
 * The only part of a profile that changes a match score.
 *
 * Naming your role comes first, because a candidate can name a job and cannot
 * name a National Occupational Standard. Searching the standards directly stays
 * underneath for anyone whose role is not in the corpus or who knows the unit
 * they want.
 *
 * The fallback is `StandardPicker` itself, not a copy of it. This section used
 * to carry its own fork of that search, which had lost the NOS code and the
 * no-results state -- the two things the picker exists to show.
 */
export function SkillsSection({ profile }: { profile: Profile | null }) {
  const t = useTranslations("profilePage");
  const { addSkill, removeSkill } = useProfileMutations();
  const [proficiency, setProficiency] = useState(3);

  const held = new Set((profile?.skills ?? []).map((s) => s.skill.slug));

  return (
    <section className="rounded-xl border border-border-token bg-surface p-6">
      <h2 className="text-base font-semibold">{t("skillsTitle")}</h2>
      <p className="mt-1 text-sm text-muted">{t("skillsSubtitle")}</p>

      <div className="mt-4">
        <RolePicker held={held} />
      </div>

      <div className="mt-6 border-t border-border-token pt-5">
        <h3 className="text-sm font-medium">{t("roles.fallbackTitle")}</h3>
        <p className="mt-1 text-xs text-muted">{t("roles.fallbackBody")}</p>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <span className="whitespace-nowrap text-muted">{t("proficiencyLabel")}</span>
          <Select
            value={proficiency}
            onChange={(e) => setProficiency(Number(e.target.value))}
            className="mt-0 w-auto"
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </Select>
        </label>
        <div className="mt-3">
          <StandardPicker
            chosen={held}
            placeholder={t("searchPlaceholder")}
            addLabel={t("add")}
            onSelect={(s) => addSkill.mutate({ skill_slug: s.slug, proficiency })}
          />
        </div>
      </div>

      <ul className="mt-5 space-y-2">
        {(profile?.skills ?? []).map((s) => (
          <li
            key={s.skill.slug}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-border-token bg-background px-3 py-2.5"
          >
            <span className="text-sm font-medium">
              {s.skill.name}
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
