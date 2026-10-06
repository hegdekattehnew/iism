"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { CORPUS_STATS } from "@/lib/counts";
import { useFormatCount } from "@/lib/format";

type Cell = {
  key: string;
  value: string | null;
  /** A narrower figure named underneath, only when it differs from the one above. */
  under?: { key: string; count: string } | null;
};

/** What the platform holds, and what has been done on it, counted live.
 *
 * Fetched client-side, like `LiveCount`, so a static build never depends on the
 * API being reachable — and if it is unreachable the band renders skeletons
 * rather than zeros. A zero here would be a lie about the corpus.
 *
 * **Two rows of six, three across (Sprint 51).** Six tiles on a four-column grid left a row of four and a row of two, so the numbers did not line up; the master-list
 * "states and districts" tile went because "districts with an open vacancy" says what is actually here.
 *
 * **Two rows (Sprint 50.5).** "People and work" leads, because the first question a
 * buyer asks is who is here and what has happened, and "what the platform holds" follows.
 * Where a broad and a narrow figure differ, the narrow one is named underneath -- the
 * pattern `LiveCount` set for "posted" and "open right now" -- so the number and its
 * definition arrive together. **A true zero renders `0`**, never a hidden tile: the owner
 * chose to always show the real count, and a figure that vanished when it was small would
 * read as a regression on the day it came back.
 *
 * `demo` is the API's word that these are a demonstration database's figures, and the band
 * says so. Without it a seeded database passes for a customer base.
 */
export function StatsBand() {
  const t = useTranslations("stats");
  const fmt = useFormatCount();

  const stats = useQuery({
    queryKey: CORPUS_STATS,
    // No `staleTime`: these move when somebody applies or signs up, and a figure older than
    // the thing it counts is the page saying something untrue (`lib/counts.ts`).
    queryFn: async () => {
      const { data, error } = await api.GET("/marketplace/stats", {});
      if (error || !data) throw new Error("stats unavailable");
      return data;
    },
    retry: false,
  });

  const d = stats.data;
  const wider = (broad: number | undefined, narrow: number | undefined) =>
    d && broad !== undefined && narrow !== undefined && broad > narrow ? fmt(broad) : null;

  const people: Cell[] = [
    {
      key: "jobSeekers",
      value: d ? fmt(d.job_seekers) : null,
      under: wider(d?.profiles, d?.job_seekers)
        ? { key: "signedUp", count: fmt(d!.profiles) }
        : null,
    },
    {
      key: "employers",
      value: d ? fmt(d.employers) : null,
      under:
        d && d.employers_hiring < d.employers
          ? { key: "hiringNow", count: fmt(d.employers_hiring) }
          : null,
    },
    {
      key: "providers",
      value: d ? fmt(d.providers) : null,
      under:
        d && d.providers_with_course < d.providers
          ? { key: "withCourse", count: fmt(d.providers_with_course) }
          : null,
    },
    { key: "applications", value: d ? fmt(d.applications) : null },
    { key: "hires", value: d ? fmt(d.hires) : null },
    { key: "districtsWithVacancy", value: d ? fmt(d.districts_with_vacancy) : null },
  ];

  const holds: Cell[] = [
    { key: "standards", value: d ? fmt(d.standards) : null },
    { key: "qualifications", value: d ? fmt(d.qualifications) : null },
    { key: "criteria", value: d ? fmt(d.criteria) : null },
    { key: "entryRoutes", value: d ? fmt(d.entry_routes) : null },
    { key: "awardingBodies", value: d ? fmt(d.awarding_bodies) : null },
    { key: "sectors", value: d ? fmt(d.sectors) : null },
  ];

  const grid = (cells: Cell[]) => (
    <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-3">
      {cells.map(({ key, value, under }) => (
        <div key={key}>
          <dt className="text-xs font-medium uppercase tracking-wide text-muted">{t(key)}</dt>
          <dd className="mt-1 text-2xl font-bold tabular-nums sm:text-3xl">
            {value ?? <Skeleton className="h-8 w-24" />}
          </dd>
          {under && (
            // Pre-formatted, not handed over as a number: next-intl would format it with the
            // page locale (`en`), and this page's rule is `en-IN` (`lib/format.ts`).
            <p className="mt-0.5 text-xs text-muted tabular-nums">
              {t(under.key, { count: under.count })}
            </p>
          )}
        </div>
      ))}
    </dl>
  );

  return (
    <>
      <section className="bg-background">
        <div className="mx-auto w-full max-w-5xl px-5 py-12 sm:py-16">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("peopleHeading")}</h2>
          <p className="mt-2 max-w-2xl text-base text-muted">{t("peopleSub")}</p>
          {grid(people)}
          {d?.demo && <p className="mt-6 text-xs font-medium text-warning-text">{t("demoNote")}</p>}
        </div>
      </section>

      <section className="border-y border-border-token bg-surface-muted">
        <div className="mx-auto w-full max-w-5xl px-5 py-12 sm:py-16">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("heading")}</h2>
          <p className="mt-2 max-w-2xl text-base text-muted">{t("sub")}</p>
          {grid(holds)}
          <p className="mt-8 text-xs text-muted">{t("footnote")}</p>
        </div>
      </section>
    </>
  );
}
