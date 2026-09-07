"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Button } from "@/components/ui";
import { api } from "@/lib/api";

/**
 * Search the national taxonomy and pick one standard.
 *
 * Extracted from the candidate profile's skills section, which had the search
 * mechanics right and the shape wrong — it called `useProfileMutations()`
 * directly, so it could only ever add a skill to `/me/profile`. An employer
 * describing a vacancy needs exactly the same search and a different verb.
 *
 * **The code is shown, not just the name.** `HSS/N5134` is what an assessor, a
 * certificate and a qualification pack all say; a picker offering only names
 * asks an employer to trust a string match they cannot check.
 */

export type Standard = {
  slug: string;
  name_en: string;
  name_hi?: string | null;
  nos_code?: string | null;
  nsqf_level?: number | null;
  matched_on?: string | null;
  match_kind?: string;
};

export function StandardPicker({
  onSelect,
  chosen,
  placeholder,
  addLabel,
}: {
  onSelect: (standard: Standard) => void;
  /** Slugs already picked, so the same standard cannot be added twice. */
  chosen: Set<string>;
  placeholder: string;
  addLabel: string;
}) {
  const ts = useTranslations("skillsPage");
  const isHi = useLocale() === "hi";
  const [query, setQuery] = useState("");
  // The input stays responsive while the request lags behind it, which matters
  // on the low-end Android this is built for.
  const deferred = useDeferredValue(query.trim());

  const search = useQuery({
    queryKey: ["standard-search", deferred],
    enabled: deferred.length > 0,
    queryFn: async () =>
      (
        await api.GET("/skills/search", {
          params: { query: { q: deferred, limit: 8 } },
        })
      ).data ?? [],
  });

  return (
    <div>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full rounded-lg border border-border-token bg-background px-4 py-2.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      />

      {deferred && (
        <ul className="mt-2 space-y-1.5">
          {(search.data ?? []).map((s) => (
            <li
              key={s.slug}
              className="flex items-center gap-3 rounded-lg border border-border-token bg-background px-3 py-2"
            >
              <span className="min-w-0 flex-1 text-sm">
                <span>{isHi && s.name_hi ? s.name_hi : s.name_en}</span>
                {s.nos_code && (
                  <span className="ml-2 font-mono text-[11px] text-muted">
                    {s.nos_code}
                  </span>
                )}
                {s.matched_on && s.match_kind === "alias" && (
                  // Shown so a transliterated hit does not look like a mistake.
                  <span className="ml-2 block text-xs text-brand">
                    {ts("matchedVia", { term: s.matched_on })}
                  </span>
                )}
              </span>
              <Button
                size="sm"
                variant="secondary"
                disabled={chosen.has(s.slug)}
                onClick={() => onSelect(s as Standard)}
              >
                {addLabel}
              </Button>
            </li>
          ))}
          {search.isFetched && (search.data ?? []).length === 0 && (
            <li className="px-1 py-2 text-sm text-muted">{ts("noResults")}</li>
          )}
        </ul>
      )}
    </div>
  );
}
