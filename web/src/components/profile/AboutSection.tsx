"use client";

import { useTranslations } from "next-intl";

import { Check, Field, Select, Text } from "@/components/profile/fields";
import { Button } from "@/components/ui";
import {
  EDUCATION_LEVELS,
  EMPLOYMENT_TYPES,
  GENDERS,
  NOTICE,
  type Profile,
  useProfileMutations,
} from "@/lib/profile";

/** Core details and preferences. Uncontrolled and keyed on the loaded profile,
 *  so a background refetch can never overwrite what is being typed. */
export function AboutSection({ profile }: { profile: Profile | null }) {
  const t = useTranslations("profilePage");
  const f = useTranslations("profilePage.fields");
  const ts = useTranslations("profilePage.sections");
  const tj = useTranslations("jobsPage");
  const { saveDetails } = useProfileMutations();

  const submit = (form: FormData) => {
    const s = (k: string) => ((form.get(k) as string) || "").trim() || null;
    const n = (k: string) => (form.get(k) ? Number(form.get(k)) : null);
    saveDetails.mutate({
      full_name: s("full_name"),
      headline: s("headline"),
      location_state: s("location_state"),
      location_district: s("location_district"),
      years_experience: n("years_experience") ?? 0,
      education_level: s("education_level"),
      date_of_birth: s("date_of_birth"),
      gender: s("gender"),
      willing_to_relocate: form.get("willing_to_relocate") === "on",
      preferred_employment_type: s("preferred_employment_type"),
      expected_salary_min_inr: n("expected_salary_min_inr"),
      expected_salary_max_inr: n("expected_salary_max_inr"),
      notice_period: s("notice_period"),
    });
  };

  return (
    <form
      key={profile?.id ?? "loading"}
      onSubmit={(e) => {
        e.preventDefault();
        submit(new FormData(e.currentTarget));
      }}
      className="space-y-6"
    >
      <section className="rounded-xl border border-border-token bg-surface p-6">
        <h2 className="text-base font-semibold">{ts("about")}</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={f("fullName")} className="sm:col-span-2">
            <Text name="full_name" defaultValue={profile?.full_name ?? ""} maxLength={120} />
          </Field>
          <Field label={t("headline")} className="sm:col-span-2">
            <Text name="headline" defaultValue={profile?.headline ?? ""} placeholder={t("headlinePlaceholder")} maxLength={160} />
          </Field>
          <Field label={t("state")}>
            <Text name="location_state" defaultValue={profile?.location_state ?? ""} />
          </Field>
          <Field label={t("district")}>
            <Text name="location_district" defaultValue={profile?.location_district ?? ""} />
          </Field>
          <Field label={t("experience")}>
            <Text type="number" name="years_experience" min={0} max={60} defaultValue={profile?.years_experience ?? 0} />
          </Field>
          <Field label={t("education")}>
            <Select name="education_level" defaultValue={profile?.education_level ?? ""}>
              <option value="">—</option>
              {EDUCATION_LEVELS.map((l) => (
                <option key={l} value={l}>{t(`educationLevel.${l}`)}</option>
              ))}
            </Select>
          </Field>
          <Field label={f("dateOfBirth")}>
            <Text type="date" name="date_of_birth" defaultValue={profile?.date_of_birth ?? ""} />
          </Field>
          <Field label={f("gender")} hint={t("genderNote")}>
            <Select name="gender" defaultValue={profile?.gender ?? ""}>
              <option value="">—</option>
              {GENDERS.map((g) => (
                <option key={g} value={g}>{t(`gender.${g}`)}</option>
              ))}
            </Select>
          </Field>
        </div>
      </section>

      <section className="rounded-xl border border-border-token bg-surface p-6">
        <h2 className="text-base font-semibold">{ts("preferences")}</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={f("employmentType")}>
            <Select name="preferred_employment_type" defaultValue={profile?.preferred_employment_type ?? ""}>
              <option value="">—</option>
              {EMPLOYMENT_TYPES.map((e) => (
                <option key={e} value={e}>{tj(`employmentType.${e}`)}</option>
              ))}
            </Select>
          </Field>
          <Field label={f("noticePeriod")}>
            <Select name="notice_period" defaultValue={profile?.notice_period ?? ""}>
              <option value="">—</option>
              {NOTICE.map((n) => (
                <option key={n} value={n}>{t(`notice.${n}`)}</option>
              ))}
            </Select>
          </Field>
          <Field label={f("salaryMin")}>
            <Text type="number" name="expected_salary_min_inr" min={0} defaultValue={profile?.expected_salary_min_inr ?? ""} />
          </Field>
          <Field label={f("salaryMax")}>
            <Text type="number" name="expected_salary_max_inr" min={0} defaultValue={profile?.expected_salary_max_inr ?? ""} />
          </Field>
          <div className="sm:col-span-2">
            <Check name="willing_to_relocate" label={f("relocate")} defaultChecked={profile?.willing_to_relocate ?? false} />
          </div>
        </div>
      </section>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saveDetails.isPending}>
          {saveDetails.isPending ? t("saving") : t("save")}
        </Button>
        {saveDetails.isSuccess && (
          <span className="text-sm text-emerald-600 dark:text-emerald-400">{t("saved")}</span>
        )}
      </div>
    </form>
  );
}
