"use client";

import { useTranslations } from "next-intl";

import { StatGrid, useCorpusStats, type Cell } from "@/components/stats-shared";
import { useFormatCount } from "@/lib/format";

/**
 * What the platform holds, counted live: the standards, qualification packs, criteria, awarding
 * bodies and sectors the whole product is built on.
 *
 * It was the homepage's second band until Sprint 70 (UI-01/02). "Built on the national framework"
 * and "238,370 assessable criteria" prove the product's depth to a funder or an employer; to a
 * person looking for a ward-boy job they are vocabulary they do not have, in the way of the one
 * thing they came to do. It lives on About now, where that reader looks. Same query, same six
 * tiles, same footnote: a figure here says exactly what it counts, and a skeleton, never a zero,
 * stands in while it is unknown.
 */
export function FrameworkBand() {
  const t = useTranslations("stats");
  const fmt = useFormatCount();
  const d = useCorpusStats().data;

  const holds: Cell[] = [
    { key: "standards", value: d ? fmt(d.standards) : null },
    { key: "qualifications", value: d ? fmt(d.qualifications) : null },
    { key: "criteria", value: d ? fmt(d.criteria) : null },
    { key: "entryRoutes", value: d ? fmt(d.entry_routes) : null },
    { key: "awardingBodies", value: d ? fmt(d.awarding_bodies) : null },
    { key: "sectors", value: d ? fmt(d.sectors) : null },
  ];

  return (
    <section className="border-y border-border-token bg-surface-muted">
      <div className="mx-auto w-full max-w-5xl px-5 py-12 sm:py-16">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("heading")}</h2>
        <p className="mt-2 max-w-2xl text-base text-muted">{t("sub")}</p>
        <StatGrid cells={holds} />
        <p className="mt-8 text-xs text-muted">{t("footnote")}</p>
      </div>
    </section>
  );
}
