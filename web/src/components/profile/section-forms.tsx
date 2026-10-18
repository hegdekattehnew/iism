"use client";

import { useTranslations } from "next-intl";

import { Area, Check, Field, Select, Text } from "@/components/profile/fields";
import { linkedStandard, str } from "@/components/profile/SectionEditor";
import { StandardPicker } from "@/components/StandardPicker";
import { Button } from "@/components/ui";
import { EDUCATION_LEVELS, LANG_PROFICIENCY } from "@/lib/profile";

/**
 * The field sets of the four repeating profile sections (Sprint 79, BL-19.10).
 *
 * Their own module, loaded the first time a section's form is opened (`LazyForm` in `SectionEditor`):
 * four forms of fields are a good deal of code and nobody sees one until they press "Add" or "Edit",
 * while `/profile` is the route closest to the first-load ceiling. The limits stay literal beside
 * each field, where `constraints.test.ts` reads them.
 */

type FormProps = {
  d: Record<string, unknown>;
  set: (patch: Record<string, unknown>) => void;
};

/**
 * Link a certification to the national standard it covers.
 *
 * Without this the operator's certification queue could never hold anything:
 * it lists only credentials that name a standard, and no screen let a candidate
 * name one. Linking is what lets a reviewer verify the certificate, which turns
 * that skill from self-declared into certified and gives it more weight in a
 * match.
 */
function CertificationStandard({
  draft,
  set,
}: {
  draft: Record<string, unknown>;
  set: (patch: Record<string, unknown>) => void;
}) {
  const f = useTranslations("profilePage.fields");
  const linked = linkedStandard(draft);

  return (
    <div className="sm:col-span-2">
      <p className="text-sm font-medium">{f("certStandard")}</p>
      {linked ? (
        <div className="mt-1 flex flex-wrap items-center gap-3 rounded-lg border border-border-token bg-background px-3 py-2 text-sm">
          <span className="min-w-0 flex-1">
            {linked.name}
            {linked.nos_code && (
              <span className="ml-2 font-mono text-xs text-muted">{linked.nos_code}</span>
            )}
          </span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => set({ skill_slug: null, skill: null })}
          >
            {f("certStandardRemove")}
          </Button>
        </div>
      ) : (
        // Enter in the search box would otherwise submit the whole certificate.
        <div
          className="mt-1"
          onKeyDown={(e) => {
            if (e.key === "Enter") e.preventDefault();
          }}
        >
          <StandardPicker
            chosen={new Set()}
            placeholder={f("certStandardSearch")}
            addLabel={f("certStandardLink")}
            onSelect={(s) =>
              set({
                skill_slug: s.slug,
                skill: { slug: s.slug, name: s.name, nos_code: s.nos_code ?? null },
              })
            }
          />
        </div>
      )}
      <p className="mt-1 text-xs text-muted">{f("certStandardHint")}</p>
    </div>
  );
}


function ExperienceForm({ d, set }: FormProps) {
  const f = useTranslations("profilePage.fields");
  return (
    <>
      <Field label={f("employer")}>
        <Text required value={str(d, "employer_name")} maxLength={120} onChange={(e) => set({ employer_name: e.target.value })} />
      </Field>
      <Field label={f("roleTitle")}>
        <Text required value={str(d, "role_title")} maxLength={120} onChange={(e) => set({ role_title: e.target.value })} />
      </Field>
      <Field label={f("location")}>
        <Text value={str(d, "location")} maxLength={120} onChange={(e) => set({ location: e.target.value })} />
      </Field>
      <Field label={f("startedOn")}>
        <Text type="date" required value={str(d, "started_on")} onChange={(e) => set({ started_on: e.target.value })} />
      </Field>
      {!d.is_current && (
        <Field label={f("endedOn")}>
          <Text type="date" value={str(d, "ended_on")} onChange={(e) => set({ ended_on: e.target.value })} />
        </Field>
      )}
      <div className="self-end">
        <Check
          label={f("current")}
          checked={Boolean(d.is_current)}
          onChange={(e) => set({ is_current: e.target.checked, ended_on: null })}
        />
      </div>
      <Field label={f("description")} className="sm:col-span-2">
        <Area value={str(d, "description")} maxLength={1000} onChange={(e) => set({ description: e.target.value })} />
      </Field>
    </>
  );
}

function EducationForm({ d, set }: FormProps) {
  const f = useTranslations("profilePage.fields");
  const t = useTranslations("profilePage");
  return (
    <>
      <Field label={f("qualification")}>
        <Text required value={str(d, "qualification")} maxLength={160} onChange={(e) => set({ qualification: e.target.value })} />
      </Field>
      <Field label={f("institution")}>
        <Text value={str(d, "institution")} maxLength={160} onChange={(e) => set({ institution: e.target.value })} />
      </Field>
      <Field label={f("specialisation")}>
        <Text value={str(d, "specialisation")} maxLength={120} onChange={(e) => set({ specialisation: e.target.value })} />
      </Field>
      <Field label={f("yearCompleted")}>
        <Text type="number" min={1950} max={2100} value={str(d, "year_completed")} onChange={(e) => set({ year_completed: e.target.value ? Number(e.target.value) : null })} />
      </Field>
      <Field label={t("education")}>
        <Select value={str(d, "education_level")} onChange={(e) => set({ education_level: e.target.value || null })}>
          <option value="">—</option>
          {EDUCATION_LEVELS.map((l) => (
            <option key={l} value={l}>{t(`educationLevel.${l}`)}</option>
          ))}
        </Select>
      </Field>
      <div className="self-end">
        <Check label={f("pursuing")} checked={Boolean(d.is_pursuing)} onChange={(e) => set({ is_pursuing: e.target.checked })} />
      </div>
    </>
  );
}

function CertificationForm({ d, set }: FormProps) {
  const f = useTranslations("profilePage.fields");
  return (
    <>
      <Field label={f("certName")}>
        <Text required value={str(d, "name")} maxLength={160} onChange={(e) => set({ name: e.target.value })} />
      </Field>
      <Field label={f("issuingBody")}>
        <Text value={str(d, "issuing_body")} maxLength={160} onChange={(e) => set({ issuing_body: e.target.value })} />
      </Field>
      <Field label={f("credentialId")}>
        <Text value={str(d, "credential_id")} maxLength={80} onChange={(e) => set({ credential_id: e.target.value })} />
      </Field>
      <Field label={f("nsqfLevel")}>
        <Text type="number" min={1} max={10} value={str(d, "nsqf_level")} onChange={(e) => set({ nsqf_level: e.target.value ? Number(e.target.value) : null })} />
      </Field>
      <Field label={f("issuedOn")}>
        <Text type="date" value={str(d, "issued_on")} onChange={(e) => set({ issued_on: e.target.value })} />
      </Field>
      <Field label={f("expiresOn")}>
        <Text type="date" value={str(d, "expires_on")} onChange={(e) => set({ expires_on: e.target.value })} />
      </Field>
      <CertificationStandard draft={d} set={set} />
    </>
  );
}

function LanguageForm({ d, set }: FormProps) {
  const f = useTranslations("profilePage.fields");
  const t = useTranslations("profilePage");
  return (
    <>
      <Field label={f("language")}>
        <Text required value={str(d, "language")} minLength={2} maxLength={40} onChange={(e) => set({ language: e.target.value })} />
      </Field>
      <Field label={f("proficiency")}>
        <Select value={str(d, "proficiency")} onChange={(e) => set({ proficiency: e.target.value })}>
          {LANG_PROFICIENCY.map((p) => (
            <option key={p} value={p}>{t(`langProficiency.${p}`)}</option>
          ))}
        </Select>
      </Field>
      <div className="flex gap-4 sm:col-span-2">
        <Check label={f("canRead")} checked={Boolean(d.can_read)} onChange={(e) => set({ can_read: e.target.checked })} />
        <Check label={f("canWrite")} checked={Boolean(d.can_write)} onChange={(e) => set({ can_write: e.target.checked })} />
      </div>
    </>
  );
}

const FORMS = {
  experiences: ExperienceForm,
  educations: EducationForm,
  certifications: CertificationForm,
  languages: LanguageForm,
} as const;

export function SectionForm({ collection, d, set }: FormProps & { collection: keyof typeof FORMS }) {
  const Form = FORMS[collection];
  return <Form d={d} set={set} />;
}
