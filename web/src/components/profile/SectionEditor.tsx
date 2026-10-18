"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { EntryRow } from "@/components/profile/fields";
import type { SectionForm } from "@/components/profile/section-forms";
import { Button } from "@/components/ui";
import { type Collection, type Profile, useProfileMutations } from "@/lib/profile";
import { detailOf, statusOf } from "@/lib/http";

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
      // 409 keeps its own sentence -- "that entry already exists" is clearer
      // than the server's phrasing. Everything else shows what the server
      // actually said: this one editor drives six collections with thirteen
      // length limits between them, and "check the fields" names none of them.
      setError(
        statusOf(e) === 409 ? te("duplicate") : (detailOf(e) ?? te("generic")),
      );
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
                onRemove={() => {
                  setError(null);
                  removeEntry.mutate(
                    { collection, id: e.id },
                    // The banner above exists and the delete path never wrote
                    // to it, so a refused removal was silent.
                    { onError: (err) => setError(detailOf(err) ?? te("generic")) },
                  );
                }}
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
            <p role="alert" className="text-sm text-danger-text sm:col-span-2">
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


/**
 * A section's fields, fetched the first time a form is opened (`section-forms.tsx`). Opening a form
 * is the person's own act, so nothing on the page moves while the chunk arrives; the slot holds the
 * height of one field until it does.
 */
function LazyForm(props: React.ComponentProps<typeof SectionForm>) {
  const [loaded, setLoaded] = useState<typeof import("@/components/profile/section-forms") | null>(null);
  useEffect(() => {
    let live = true;
    void import("@/components/profile/section-forms").then((m) => live && setLoaded(m));
    return () => {
      live = false;
    };
  }, []);
  return loaded ? <loaded.SectionForm {...props} /> : <div className="min-h-11 sm:col-span-2" aria-busy="true" />;
}

// ---------------------------------------------------------------- per-section
// Field sets and row summaries, kept beside the generic editor so adding a
// section is one entry here rather than a new component.

export const str = (d: Record<string, unknown>, k: string) => (d[k] as string) ?? "";

type LinkedStandard = { slug: string; name: string; nos_code?: string | null };

/** The standard a certification is linked to, from either shape it can have:
 *  the saved entry carries a `skill` object, a draft being edited carries the
 *  `skill_slug` it will send. */
export function linkedStandard(entry: Record<string, unknown>): LinkedStandard | null {
  const skill = entry.skill as LinkedStandard | null | undefined;
  return skill ?? null;
}

export function useSectionDefs(profile: Profile | null) {
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
        <LazyForm collection="experiences" d={d} set={set} />
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
        <LazyForm collection="educations" d={d} set={set} />
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
        <LazyForm collection="certifications" d={d} set={set} />
      ),
      summarise: (e: Entry) => ({
        title: e.name as string,
        subtitle: (e.issuing_body as string) || null,
        meta:
          [
            (e.credential_id as string) || null,
            linkedStandard(e)?.name ?? null,
          ]
            .filter(Boolean)
            .join(" · ") || null,
      }),
    },
    {
      collection: "languages" as Collection,
      title: ts("languages"),
      entries: list<Entry>("languages"),
      blank: { language: "", proficiency: "conversational", can_read: true, can_write: true },
      renderForm: (d: Record<string, unknown>, set: (p: Record<string, unknown>) => void) => (
        <LazyForm collection="languages" d={d} set={set} />
      ),
      summarise: (e: Entry) => ({
        title: e.language as string,
        subtitle: t(`langProficiency.${e.proficiency as string}`),
      }),
    },
  ];
}
