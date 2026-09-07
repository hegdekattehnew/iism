"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Area, Field, Select, Text } from "@/components/profile/fields";
import { type Standard, StandardPicker } from "@/components/StandardPicker";
import { Badge, Button, Card, CardBody } from "@/components/ui";
import type { JobPayload, OrgJob } from "@/lib/org";

/**
 * Composing a vacancy against the national taxonomy.
 *
 * The form itself is uncontrolled with a `key`, exactly as the candidate
 * profile's About section is, so a background refetch cannot overwrite what
 * someone is typing. The required standards are the part that is genuinely
 * different: each carries an importance and a mandatory flag, and those two
 * fields are what make a defensible match score possible at all.
 */

type Requirement = {
  skill_slug: string;
  name: string;
  nos_code?: string | null;
  importance: number;
  is_mandatory: boolean;
};

function toRequirements(job: OrgJob | null): Requirement[] {
  return (job?.skills ?? []).map((s) => ({
    skill_slug: s.skill.slug,
    name: s.skill.name_en,
    nos_code: s.skill.nos_code,
    importance: s.importance,
    is_mandatory: s.is_mandatory,
  }));
}

export function JobEditor({
  job,
  saving,
  onSave,
  onCancel,
}: {
  job: OrgJob | null;
  saving: boolean;
  onSave: (payload: JobPayload) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("employerWorkspace");
  const [requirements, setRequirements] = useState<Requirement[]>(() =>
    toRequirements(job),
  );

  const chosen = new Set(requirements.map((r) => r.skill_slug));

  const add = (s: Standard) =>
    setRequirements((rs) => [
      ...rs,
      {
        skill_slug: s.slug,
        name: s.name_en,
        nos_code: s.nos_code,
        importance: 3,
        is_mandatory: false,
      },
    ]);

  const patch = (slug: string, change: Partial<Requirement>) =>
    setRequirements((rs) =>
      rs.map((r) => (r.skill_slug === slug ? { ...r, ...change } : r)),
    );

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    // Empty strings become null, or the API rejects "" where it wants a number
    // or nothing at all — the same coercion the profile editor needs.
    const s = (k: string) =>
      (String(form.get(k) ?? "").trim() || null) as string | null;
    const n = (k: string) => {
      const raw = s(k);
      return raw === null ? null : Number(raw);
    };

    onSave({
      title_en: String(form.get("title_en") ?? "").trim(),
      title_hi: s("title_hi"),
      description_en: s("description_en"),
      description_hi: s("description_hi"),
      location_state: s("location_state"),
      location_district: s("location_district"),
      employment_type: (s("employment_type") ??
        "full_time") as JobPayload["employment_type"],
      experience_min_years: n("experience_min_years") ?? 0,
      experience_max_years: n("experience_max_years"),
      salary_min_inr: n("salary_min_inr"),
      salary_max_inr: n("salary_max_inr"),
      nsqf_level_min: n("nsqf_level_min"),
      skills: requirements.map((r) => ({
        skill_slug: r.skill_slug,
        importance: r.importance,
        is_mandatory: r.is_mandatory,
      })),
    });
  };

  return (
    <Card>
      <CardBody>
        <form onSubmit={submit} key={job?.slug ?? "new"}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("titleEn")} className="sm:col-span-2">
              <Text
                name="title_en"
                required
                defaultValue={job?.title_en ?? ""}
              />
            </Field>
            <Field
              label={t("titleHi")}
              className="sm:col-span-2"
              hint={t("titleHiHint")}
            >
              <Text name="title_hi" defaultValue={job?.title_hi ?? ""} />
            </Field>
            <Field label={t("descriptionEn")} className="sm:col-span-2">
              <Area
                name="description_en"
                defaultValue={job?.description_en ?? ""}
              />
            </Field>
            <Field label={t("state")}>
              <Text
                name="location_state"
                defaultValue={job?.location_state ?? ""}
              />
            </Field>
            <Field label={t("district")}>
              <Text
                name="location_district"
                defaultValue={job?.location_district ?? ""}
              />
            </Field>
            <Field label={t("employmentType")}>
              <Select
                name="employment_type"
                defaultValue={job?.employment_type ?? "full_time"}
              >
                {["full_time", "part_time", "contract", "apprenticeship"].map(
                  (v) => (
                    <option key={v} value={v}>
                      {t(`employment.${v}`)}
                    </option>
                  ),
                )}
              </Select>
            </Field>
            <Field label={t("nsqfMin")} hint={t("nsqfMinHint")}>
              {/* step 0.5: the corpus is 38% half-levels, and a whole-number
                  spinner silently hides them. */}
              <Text
                name="nsqf_level_min"
                type="number"
                min={1}
                max={10}
                step={0.5}
                defaultValue={job?.nsqf_level_min ?? ""}
              />
            </Field>
            <Field label={t("experienceMin")}>
              <Text
                name="experience_min_years"
                type="number"
                min={0}
                max={60}
                defaultValue={job?.experience_min_years ?? 0}
              />
            </Field>
            <Field label={t("experienceMax")}>
              <Text
                name="experience_max_years"
                type="number"
                min={0}
                max={60}
                defaultValue={job?.experience_max_years ?? ""}
              />
            </Field>
            <Field label={t("salaryMin")}>
              <Text
                name="salary_min_inr"
                type="number"
                min={0}
                defaultValue={job?.salary_min_inr ?? ""}
              />
            </Field>
            <Field label={t("salaryMax")}>
              <Text
                name="salary_max_inr"
                type="number"
                min={0}
                defaultValue={job?.salary_max_inr ?? ""}
              />
            </Field>
          </div>

          <div className="mt-8 border-t border-border-token pt-6">
            <h3 className="text-base font-semibold">{t("standardsTitle")}</h3>
            <p className="mt-1 text-sm text-muted">{t("standardsSubtitle")}</p>

            <div className="mt-4">
              <StandardPicker
                onSelect={add}
                chosen={chosen}
                placeholder={t("standardsSearch")}
                addLabel={t("addStandard")}
              />
            </div>

            {requirements.length === 0 ? (
              <p className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
                {t("noStandardsWarning")}
              </p>
            ) : (
              <ul className="mt-4 space-y-2">
                {requirements.map((r) => (
                  <li
                    key={r.skill_slug}
                    className="rounded-lg border border-border-token bg-background px-3 py-2.5"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <span className="min-w-0 flex-1 text-sm">
                        {r.name}
                        {r.nos_code && (
                          <span className="ml-2 font-mono text-[11px] text-muted">
                            {r.nos_code}
                          </span>
                        )}
                      </span>
                      {r.is_mandatory && (
                        <Badge tone="warn">{t("mandatory")}</Badge>
                      )}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-4">
                      <label className="flex items-center gap-2 text-xs text-muted">
                        {t("importance")}
                        <Select
                          value={r.importance}
                          onChange={(e) =>
                            patch(r.skill_slug, {
                              importance: Number(e.target.value),
                            })
                          }
                          className="mt-0 w-auto py-1"
                        >
                          {[1, 2, 3, 4, 5].map((v) => (
                            <option key={v} value={v}>
                              {v}
                            </option>
                          ))}
                        </Select>
                      </label>
                      <label className="flex items-center gap-2 text-xs text-muted">
                        <input
                          type="checkbox"
                          checked={r.is_mandatory}
                          onChange={(e) =>
                            patch(r.skill_slug, {
                              is_mandatory: e.target.checked,
                            })
                          }
                          className="h-4 w-4 rounded border-border-token accent-brand"
                        />
                        {t("mandatoryHint")}
                      </label>
                      <button
                        type="button"
                        onClick={() =>
                          setRequirements((rs) =>
                            rs.filter((x) => x.skill_slug !== r.skill_slug),
                          )
                        }
                        className="ml-auto text-xs text-muted hover:text-rose-600 hover:underline"
                      >
                        {t("remove")}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <Button type="submit" disabled={saving}>
              {saving ? t("saving") : t("save")}
            </Button>
            <Button type="button" variant="secondary" onClick={onCancel}>
              {t("cancel")}
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
