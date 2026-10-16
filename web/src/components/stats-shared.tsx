"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { CORPUS_STATS } from "@/lib/counts";

export type Cell = {
  key: string;
  value: string | null;
  /** A narrower figure named underneath, only when it differs from the one above. */
  under?: { key: string; count: string } | null;
  /** This tile may grow a line underneath once the figures arrive: keep the room for it from the start. */
  reserve?: boolean;
};

/**
 * The live corpus figures, one query shared by the homepage's people band and the About page's
 * framework band (Sprint 70 split them: the framework figures speak to a funder, not to a person
 * looking for work, so they live where that reader looks).
 *
 * No `staleTime`: these move when somebody applies or signs up, and a figure older than the thing it
 * counts is the page saying something untrue (`lib/counts.ts`).
 */
export function useCorpusStats() {
  return useQuery({
    queryKey: CORPUS_STATS,
    queryFn: async () => {
      const { data, error } = await api.GET("/marketplace/stats", {});
      if (error || !data) throw new Error("stats unavailable");
      return data;
    },
    retry: false,
  });
}

/** Six tiles, three across from tablet width: a count that is not a multiple of the columns reads as misaligned. */
export function StatGrid({ cells }: { cells: Cell[] }) {
  const t = useTranslations("stats");
  return (
    <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-3">
      {cells.map(({ key, value, under, reserve }) => (
        <div key={key}>
          <dt className="text-xs font-medium uppercase tracking-wide text-muted">{t(key)}</dt>
          <dd className="mt-1 text-2xl font-bold tabular-nums sm:text-3xl">
            {value ?? <Skeleton className="h-8 w-24" />}
          </dd>
          {(under || reserve) && (
            // Pre-formatted, not handed over as a number: next-intl would format it with the
            // page locale (`en`), and this page's rule is `en-IN` (`lib/format.ts`).
            // A `<dd>`, not a `<p>`: a `<dl>` may hold only `dt`/`dd` groups, and axe fails the
            // whole list otherwise. It appears only when a secondary figure exists, so an
            // empty database never showed it (Sprint 52's browser run did).
            // `min-h-4` is the room the line takes, held while the figures load and when a tile has no
            // narrower figure: without it every tile below the first row dropped 16px when they
            // arrived (Sprint 54: the homepage scored 0.11 of layout shift on a phone, in Hindi).
            <dd className="mt-0.5 min-h-4 text-xs text-muted tabular-nums">
              {under ? t(under.key, { count: under.count }) : null}
            </dd>
          )}
        </div>
      ))}
    </dl>
  );
}
