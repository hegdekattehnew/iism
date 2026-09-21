"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Area, Check, Field, EntryRow, Select, Text } from "@/components/profile/fields";
import { Button } from "@/components/ui";
import {
  type Collection,
  EDUCATION_LEVELS,
  LANG_PROFICIENCY,
  type Profile,
  useProfileMutations,
} from "@/lib/profile";

type Entry = Record<string, unknown> & { id: string };

/**
 * One repeating profile section. All six collections share this component:
 * they differ only in their fields and how a saved row is summarised, so
 * six near-identical editors would only drift apart.
 */
export function SectionEditor({
  collection,
  title,
  entries,
  renderForm,
  summarise,
  blank,
}: {
  collection: Collection;
  title: string;
  entries: Entry[];
  renderForm: (
    draft: Record<string, unknown>,
    set: (patch: Record<string, unknown>) => void,
  ) => React.ReactNode;
  summarise: (e: Entry) => { title: string; subtitle?: string | null; meta?: string | null };
  blank: Record<string, unknown>;
}) {
  const t = useTranslations("profilePage.sections");
  const te = useTranslations("profilePage.errors");
  const { addEntry, updateEntry, removeEntry } = useProfileMutations();

  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>(blank);
  const [error, setError] = useState<string | null>(null);

  const set = (patch: Record<string, unknown>) => setDraft((d) => ({ ...d, ...patch }));

  const close = () => {
    setOpen(false);
    setEditingId(null);
    setDraft(blank);
    setError(null);
  };

  const submit = async () => {
    setError(null);
    // Empty strings must become null, or the API rejects "" for optional dates.
    const body = Object.fromEntries(
      Object.entries(draft).map(([k, v]) => [k, v === "" ? null : v]),
    );
    try {
      if (editingId) {
        await updateEntry.mutateAsync({ collection, id: editingId, body });
      } else {
        await addEntry.mutateAsync({ collection, body });
      }
      close();
    } catch (e) {
      setError(String((e as Error).message) === "409" ? te("duplicate") : te("generic"));
    }
  };

  return (
    <section className="rounded-xl border border-border-token bg-surface p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">{title}</h2>
        {!open && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setDraft(blank);
              setEditingId(null);
              setOpen(true);
            }}
          >
            + {t("addEntry")}
          </Button>
        )}
      </div>

      {entries.length === 0 && !open && (
        <p className="mt-3 text-sm text-muted">{t("empty")}</p>
      )}

      {entries.length > 0 && (
        <ul className="mt-4 space-y-2">
          {entries.map((e) => {
            const s = summarise(e);
            return (
              <EntryRow
                key={e.id}
                title={s.title}
                subtitle={s.subtitle}
                meta={s.meta}
                editLabel={t("edit")}
                removeLabel={t("delete")}
                onEdit={() => {
                  // The id travels in the URL, not the body.
                  const rest = Object.fromEntries(
                    Object.entries(e).filter(([k]) => k !== "id"),
                  );
                  setDraft(rest);
                  setEditingId(e.id);
                  setOpen(true);
                }}
                onRemove={() => removeEntry.mutate({ collection, id: e.id })}
              />
            );
          })}
        </ul>
      )}

      {open && (
        <form
          className="mt-4 grid grid-cols-1 gap-4 rounded-lg border border-border-token bg-background p-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          {renderForm(draft, set)}
          {error && (
            <p role="alert" className="text-sm text-rose-600 sm:col-span-2">
              {error}
            </p>
          )}
          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" size="sm" disabled={addEntry.isPending || updateEntry.isPending}>
              {t("saveSection")}
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={close}>
              {t("cancel")}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- per-section
// Field sets and row summaries, kept beside the generic editor so adding a
// section is one entry here rather than a new component.

const str = (d: Record<string, unknown>, k: string) => (d[k] as string) ?? "";

export function useSectionDefs(profile: Profile | null) {
  const f = useTranslations("profilePage.fields");
  const t = useTranslations("profilePage");
  const ts = useTranslations("profilePage.sections");
  const list = <T,>(k: keyof Profile): T[] => ((profile?.[k] ?? []) as T[]);

  return [
    {
      collection: "experiences" as Collection,
      title: ts("experience"),
      entries: list<Entry>("experiences"),
      blank: { employer_name: "", role_title: "", started_on: "", is_current: false },
      renderForm: (d: Record<string, unknown>, set: (p: Record<string, unknown>) => void) => (
        <>
          <Field label={f("employer")}>
            <Text required value={str(d, "employer_name")} onChange={(e) => set({ employer_name: e.target.value })} />
          </Field>
          <Field label={f("roleTitle")}>
            <Text required value={str(d, "role_title")} onChange={(e) => set({ role_title: e.target.value })} />
          </Field>
          <Field label={f("location")}>
            <Text value={str(d, "location")} onChange={(e) => set({ location: e.target.value })} />
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
            <Area value={str(d, "description")} onChange={(e) => set({ description: e.target.value })} />
          </Field>
        </>
      ),
      summarise: (e: Entry) => ({
        title: `${e.role_title as string} · ${e.employer_name as string}`,
        subtitle: (e.location as string) || null,
        meta: `${e.started_on as string} — ${e.is_current ? t("present") : ((e.ended_on as string) ?? "")}`,
      }),
    },
    {
      collection: "educations" as Collection,
      title: ts("education"),
      entries: list<Entry>("educations"),
      blank: { qualification: "", is_pursuing: false },
      renderForm: (d: Record<string, unknown>, set: (p: Record<string, unknown>) => void) => (
        <>
          <Field label={f("qualification")}>
            <Text required value={str(d, "qualification")} onChange={(e) => set({ qualification: e.target.value })} />
          </Field>
          <Field label={f("institution")}>
            <Text value={str(d, "institution")} onChange={(e) => set({ institution: e.target.value })} />
          </Field>
          <Field label={f("specialisation")}>
            <Text value={str(d, "specialisation")} onChange={(e) => set({ specialisation: e.target.value })} />
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
      ),
      summarise: (e: Entry) => ({
        title: e.qualification as string,
        subtitle: (e.institution as string) || null,
        meta: (e.year_completed as number)?.toString() ?? null,
      }),
    },
    {
      collection: "certifications" as Collection,
      title: ts("certifications"),
      entries: list<Entry>("certifications"),
      blank: { name: "" },
      renderForm: (d: Record<string, unknown>, set: (p: Record<string, unknown>) => void) => (
        <>
          <Field label={f("certName")}>
            <Text required value={str(d, "name")} onChange={(e) => set({ name: e.target.value })} />
          </Field>
          <Field label={f("issuingBody")}>
            <Text value={str(d, "issuing_body")} onChange={(e) => set({ issuing_body: e.target.value })} />
          </Field>
          <Field label={f("credentialId")}>
            <Text value={str(d, "credential_id")} onChange={(e) => set({ credential_id: e.target.value })} />
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
        </>
      ),
      summarise: (e: Entry) => ({
        title: e.name as string,
        subtitle: (e.issuing_body as string) || null,
        meta: (e.credential_id as string) || null,
      }),
    },
    {
      collection: "languages" as Collection,
      title: ts("languages"),
      entries: list<Entry>("languages"),
      blank: { language: "", proficiency: "conversational", can_read: true, can_write: true },
      renderForm: (d: Record<string, unknown>, set: (p: Record<string, unknown>) => void) => (
        <>
          <Field label={f("language")}>
            <Text required value={str(d, "language")} onChange={(e) => set({ language: e.target.value })} />
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
      ),
      summarise: (e: Entry) => ({
        title: e.language as string,
        subtitle: t(`langProficiency.${e.proficiency as string}`),
      }),
    },
  ];
}
