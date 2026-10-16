"use client";

import { useTranslations } from "next-intl";

import { StatGrid, useCorpusStats, type Cell } from "@/components/stats-shared";
import { useFormatCount } from "@/lib/format";

/** Who is here and what has been done on the platform, counted live.
 *
 * Fetched client-side, like `LiveCount`, so a static build never depends on the
 * API being reachable — and if it is unreachable the band renders skeletons
 * rather than zeros. A zero here would be a lie about the corpus.
 *
 * **Six tiles, three across (Sprint 51).** Six tiles on a four-column grid left a row of four and a row of two, so the numbers did not line up; the master-list
 * "states and districts" tile went because "districts with an open vacancy" says what is actually here.
 *
 * **Who is here comes first (Sprint 50.5), and since Sprint 70 it is the only band.** The first question a
 * buyer asks is who is here and what has happened; "what the platform holds" (the framework figures) moved
 * to About (`FrameworkBand`). Where a broad and a narrow figure differ, the narrow one is named underneath --
 * the pattern `LiveCount` set for "posted" and "open right now" -- so the number and its
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
  const stats = useCorpusStats();

  const d = stats.data;
  const wider = (broad: number | undefined, narrow: number | undefined) =>
    d && broad !== undefined && narrow !== undefined && broad > narrow ? fmt(broad) : null;

  const people: Cell[] = [
    {
      key: "jobSeekers",
      reserve: true,
      value: d ? fmt(d.job_seekers) : null,
      under: wider(d?.profiles, d?.job_seekers)
        ? { key: "signedUp", count: fmt(d!.profiles) }
        : null,
    },
    {
      key: "employers",
      reserve: true,
      value: d ? fmt(d.employers) : null,
      under:
        d && d.employers_hiring < d.employers
          ? { key: "hiringNow", count: fmt(d.employers_hiring) }
          : null,
    },
    {
      key: "providers",
      reserve: true,
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

  return (
    <section className="bg-background">
      <div className="mx-auto w-full max-w-5xl px-5 py-12 sm:py-16">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("peopleHeading")}</h2>
        <p className="mt-2 max-w-2xl text-base text-muted">{t("peopleSub")}</p>
        <StatGrid cells={people} />
        {d?.demo && <p className="mt-6 text-xs font-medium text-warning-text">{t("demoNote")}</p>}
      </div>
    </section>
  );
}
