"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";

import { api } from "@/lib/api";
import { MARKETPLACE_COUNTS, SKILL_COUNT } from "@/lib/counts";

type Kind = "skills" | "jobs" | "courses";

/** Real catalogue counts, fetched client-side so the static build never depends
 *  on the API being reachable.
 *
 *  **It renders its own label, which `BrowsePanels` used to own.** The jobs
 *  panel leads with how many vacancies have been posted and names how many are
 *  still open underneath -- and whether that second line appears at all is a
 *  function of the data, which a server component has never seen. That is also
 *  why there is no `secondary` render prop: a function cannot cross the RSC
 *  boundary, and a separate `JobsCount` would mean two components fetching one
 *  key and formatting numbers two ways.
 */
export function LiveCount({ kind }: { kind: Kind }) {
  const t = useTranslations("browse");
  const locale = useLocale();

  const skills = useQuery({
    queryKey: SKILL_COUNT,
    queryFn: async () => (await api.GET("/skills/count")).data ?? null,
    enabled: kind === "skills",
  });

  const marketplace = useQuery({
    queryKey: MARKETPLACE_COUNTS,
    queryFn: async () => (await api.GET("/marketplace/counts")).data ?? null,
    enabled: kind !== "skills",
  });

  // Indian grouping, the same rule `StatsBand` applies -- 21,303 not 21303.
  // The two sit within a screen of each other on the homepage, and an
  // unformatted number beside a formatted one reads as a different kind of
  // number rather than a larger one.
  const fmt = (n: number) =>
    new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(n);

  const counts = marketplace.data;
  const value =
    kind === "skills"
      ? skills.data?.count
      : kind === "jobs"
        ? counts?.jobs_posted
        : counts?.courses;

  // Only when there is something to disambiguate: with nothing closed the two
  // figures are equal and the line is noise. Gated on the **payload** rather
  // than on the comparison alone, because `undefined < undefined` would hide
  // it while loading for a reason nobody chose.
  const openNow =
    kind === "jobs" && counts != null && counts.jobs_open < counts.jobs_posted
      ? counts.jobs_open
      : null;

  return (
    <div className="mt-6">
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-semibold tabular-nums">
          {value == null ? "—" : fmt(value)}
        </span>
        <span className="text-xs text-muted">{t(`${kind}CountLabel`)}</span>
      </div>

      {openNow !== null && (
        // Pre-formatted, not handed over as a number: next-intl would format
        // it with the page locale (`en`), and this page's rule is `en-IN`.
        <p className="mt-1 text-xs text-muted tabular-nums">
          {t("jobsOpenNow", { count: fmt(openNow) })}
        </p>
      )}
    </div>
  );
}
