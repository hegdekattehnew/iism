"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Area, Field, Select, Text } from "@/components/profile/fields";
import { type Standard, StandardPicker } from "@/components/StandardPicker";
import { Button, Card, CardBody } from "@/components/ui";
import type { CoursePayload, OrgCourse } from "@/lib/org";

/**
 * Composing a course against the national taxonomy.
 *
 * A sibling of `JobEditor`, not a variant of it. The standards a course teaches
 * carry a **level taught** and nothing else — no importance, no mandatory flag —
 * because what matters about a course is whether it closes a gap and how far,
 * where a job's requirements are what a match is scored against. A course also
 * has a mode, a language, a duration and a fee, and no location at all.
 */

type Taught = {
  skill_slug: string;
  name: string;
  nos_code?: string | null;
  level_taught: number | null;
};

function toTaught(course: OrgCourse | null): Taught[] {
  return (course?.skills ?? []).map((s) => ({
    skill_slug: s.skill.slug,
    name: s.skill.name_en,
    nos_code: s.skill.nos_code,
    level_taught: s.level_taught ?? null,
  }));
}

export function CourseEditor({
  course,
  saving,
  onSave,
  onCancel,
}: {
  course: OrgCourse | null;
  saving: boolean;
  onSave: (payload: CoursePayload) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("providerWorkspace");
  const [taught, setTaught] = useState<Taught[]>(() => toTaught(course));

  const chosen = new Set(taught.map((s) => s.skill_slug));

  const add = (s: Standard) =>
    setTaught((rs) => [
      ...rs,
      {
        skill_slug: s.slug,
        name: s.name_en,
        nos_code: s.nos_code,
        level_taught: s.nsqf_level ?? null,
      },
    ]);

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
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
      mode: (s("mode") ?? "offline") as CoursePayload["mode"],
      language: (s("language") ?? "both") as CoursePayload["language"],
      duration_hours: n("duration_hours"),
      fee_inr: n("fee_inr"),
      nsqf_level: n("nsqf_level"),
      skills: taught.map((s2) => ({
        skill_slug: s2.skill_slug,
        level_taught: s2.level_taught,
      })),
    });
  };

  return (
    <Card>
      <CardBody>
        <form onSubmit={submit} key={course?.slug ?? "new"}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("titleEn")} className="sm:col-span-2">
              <Text
                name="title_en"
                required
                defaultValue={course?.title_en ?? ""}
              />
            </Field>
            <Field
              label={t("titleHi")}
              className="sm:col-span-2"
              hint={t("titleHiHint")}
            >
              <Text name="title_hi" defaultValue={course?.title_hi ?? ""} />
            </Field>
            <Field label={t("descriptionEn")} className="sm:col-span-2">
              <Area
                name="description_en"
                defaultValue={course?.description_en ?? ""}
              />
            </Field>
            <Field label={t("mode")}>
              <Select name="mode" defaultValue={course?.mode ?? "offline"}>
                {["online", "offline", "hybrid"].map((v) => (
                  <option key={v} value={v}>
                    {t(`modes.${v}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("language")}>
              <Select name="language" defaultValue={course?.language ?? "both"}>
                {["en", "hi", "both"].map((v) => (
                  <option key={v} value={v}>
                    {t(`languages.${v}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("durationHours")}>
              <Text
                name="duration_hours"
                type="number"
                min={1}
                defaultValue={course?.duration_hours ?? ""}
              />
            </Field>
            <Field label={t("fee")} hint={t("feeHint")}>
              <Text
                name="fee_inr"
                type="number"
                min={0}
                defaultValue={course?.fee_inr ?? ""}
              />
            </Field>
            <Field label={t("nsqfLevel")} hint={t("nsqfLevelHint")}>
              {/* step 0.5: the corpus is 38% half-levels, and a whole-number
                  spinner silently hides them. */}
              <Text
                name="nsqf_level"
                type="number"
                min={1}
                max={10}
                step={0.5}
                defaultValue={course?.nsqf_level ?? ""}
              />
            </Field>
          </div>

          <div className="mt-8 border-t border-border-token pt-6">
            <h3 className="text-base font-semibold">{t("teachesTitle")}</h3>
            <p className="mt-1 text-sm text-muted">{t("teachesSubtitle")}</p>

            <div className="mt-4">
              <StandardPicker
                onSelect={add}
                chosen={chosen}
                placeholder={t("standardsSearch")}
                addLabel={t("addStandard")}
              />
            </div>

            {taught.length === 0 ? (
              <p className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
                {t("noStandardsWarning")}
              </p>
            ) : (
              <ul className="mt-4 space-y-2">
                {taught.map((s) => (
                  <li
                    key={s.skill_slug}
                    className="rounded-lg border border-border-token bg-background px-3 py-2.5"
                  >
                    <span className="block text-sm">
                      {s.name}
                      {s.nos_code && (
                        <span className="ml-2 font-mono text-[11px] text-muted">
                          {s.nos_code}
                        </span>
                      )}
                    </span>
                    <div className="mt-2 flex flex-wrap items-center gap-4">
                      <label className="flex items-center gap-2 text-xs text-muted">
                        {t("levelTaught")}
                        <Select
                          value={s.level_taught ?? ""}
                          onChange={(e) =>
                            setTaught((rs) =>
                              rs.map((x) =>
                                x.skill_slug === s.skill_slug
                                  ? {
                                      ...x,
                                      level_taught: e.target.value
                                        ? Number(e.target.value)
                                        : null,
                                    }
                                  : x,
                              ),
                            )
                          }
                          className="mt-0 w-auto py-1"
                        >
                          <option value="">{t("levelUnset")}</option>
                          {[
                            1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7,
                            8, 9, 10,
                          ].map((v) => (
                            <option key={v} value={v}>
                              {v}
                            </option>
                          ))}
                        </Select>
                      </label>
                      <button
                        type="button"
                        onClick={() =>
                          setTaught((rs) =>
                            rs.filter((x) => x.skill_slug !== s.skill_slug),
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
