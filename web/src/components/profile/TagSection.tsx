"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Text } from "@/components/profile/fields";
import { Button } from "@/components/ui";
import { type Collection, useProfileMutations } from "@/lib/profile";

type Entry = { id: string } & Record<string, unknown>;

/**
 * Preferred roles and locations: short values best entered as chips rather
 * than a form with an add/edit/cancel cycle.
 */
export function TagSection({
  collection,
  title,
  hint,
  entries,
  label,
  toBody,
  render,
  secondLabel,
  toSecond,
}: {
  collection: Collection;
  title: string;
  hint?: string;
  entries: Entry[];
  label: string;
  toBody: (a: string, b: string) => Record<string, unknown>;
  render: (e: Entry) => string;
  secondLabel?: string;
  toSecond?: boolean;
}) {
  const t = useTranslations("profilePage.sections");
  const te = useTranslations("profilePage.errors");
  const { addEntry, removeEntry } = useProfileMutations();
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [error, setError] = useState<string | null>(null);

  const add = async () => {
    if (!a.trim()) return;
    setError(null);
    try {
      await addEntry.mutateAsync({ collection, body: toBody(a.trim(), b.trim()) });
      setA("");
      setB("");
    } catch (e) {
      setError((e as Error).message === "409" ? te("duplicate") : te("generic"));
    }
  };

  return (
    <section className="rounded-xl border border-border-token bg-surface p-6">
      <h2 className="text-base font-semibold">{title}</h2>
      {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Text
          value={a}
          onChange={(e) => setA(e.target.value)}
          placeholder={label}
          aria-label={label}
          className="mt-0 flex-1"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void add();
            }
          }}
        />
        {toSecond && (
          <Text
            value={b}
            onChange={(e) => setB(e.target.value)}
            placeholder={secondLabel}
            aria-label={secondLabel}
            className="mt-0 flex-1"
          />
        )}
        <Button type="button" variant="secondary" onClick={() => void add()} disabled={addEntry.isPending}>
          + {t("addEntry")}
        </Button>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-sm text-rose-600">
          {error}
        </p>
      )}

      {entries.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t("empty")}</p>
      ) : (
        <ul className="mt-4 flex flex-wrap gap-2">
          {entries.map((e) => (
            <li
              key={e.id}
              className="inline-flex items-center gap-2 rounded-lg border border-border-token bg-background px-3 py-1.5 text-sm"
            >
              {render(e)}
              <button
                type="button"
                aria-label={t("delete")}
                onClick={() => removeEntry.mutate({ collection, id: e.id })}
                className="text-muted hover:text-rose-600"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
