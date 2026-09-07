"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui";
import { api } from "@/lib/api";

/** What the platform actually holds, counted live.
 *
 * Fetched client-side, like `LiveCount`, so a static build never depends on the
 * API being reachable — and if it is unreachable the band renders skeletons
 * rather than zeros. A zero here would be a lie about the corpus.
 */
export function StatsBand() {
  const t = useTranslations("stats");
  const locale = useLocale();

  const stats = useQuery({
    queryKey: ["corpus-stats"],
    staleTime: 10 * 60_000,
    queryFn: async () => {
      const { data, error } = await api.GET("/marketplace/stats", {});
      if (error || !data) throw new Error("stats unavailable");
      return data;
    },
    retry: false,
  });

  // Indian grouping for Hindi and Indian English alike: 2,38,370 not 238,370.
  const fmt = (n: number) => new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(n);
  const d = stats.data;

  const cells: { key: string; value: string | null }[] = [
    { key: "standards", value: d ? fmt(d.standards) : null },
    { key: "qualifications", value: d ? fmt(d.qualifications) : null },
    { key: "criteria", value: d ? fmt(d.criteria) : null },
    { key: "entryRoutes", value: d ? fmt(d.entry_routes) : null },
    { key: "awardingBodies", value: d ? fmt(d.awarding_bodies) : null },
    { key: "sectors", value: d ? fmt(d.sectors) : null },
    { key: "coverage", value: d ? `${fmt(d.states)} · ${fmt(d.districts)}` : null },
  ];

  return (
    <section className="border-y border-border-token bg-surface-muted">
      <div className="mx-auto w-full max-w-5xl px-5 py-12 sm:py-16">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("heading")}</h2>
        <p className="mt-2 max-w-2xl text-base text-muted">{t("sub")}</p>

        <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
          {cells.map(({ key, value }) => (
            <div key={key}>
              <dt className="text-xs font-medium uppercase tracking-wide text-muted">
                {t(key)}
              </dt>
              <dd className="mt-1 text-2xl font-bold tabular-nums sm:text-3xl">
                {value ?? <Skeleton className="h-8 w-24" />}
              </dd>
            </div>
          ))}
        </dl>

        <p className="mt-8 text-xs text-muted">{t("footnote")}</p>
      </div>
    </section>
  );
}
