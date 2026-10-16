"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { CandidateDashboard } from "@/components/CandidateDashboard";
import { Skeleton } from "@/components/ui";
import { useCandidateDashboard } from "@/lib/profile";

/**
 * "14 matches · best 87 · profile 100% complete", and the dashboard behind a disclosure
 * (Sprint 70, UI-12).
 *
 * The matches page opened on a dashboard (a ring, a funnel, a top-five chart) and the first real
 * match started about a screen down; fifteen screens in all. Someone who came to see their matches
 * now sees them first, with the numbers one line above and the charts one tap away. The charts are
 * mounted only while open, so a person who never opens them never pays for the query behind them
 * being drawn. The figures are the dashboard's own (`match_count` is counted over every scored
 * vacancy, never a page), so this strip and the list below agree.
 *
 * Silent on error, like the dashboard it summarises: the list below already says why nothing loaded.
 */
export function MatchesStrip() {
  const t = useTranslations("matchesPage");
  const dashboard = useCandidateDashboard();
  const [open, setOpen] = useState(false);

  if (dashboard.isPending) return <Skeleton className="h-6 w-72 max-w-full" />;
  if (dashboard.isError) return null;

  const d = dashboard.data;
  const parts = [
    t("strip.matches", { count: d.match_count }),
    d.best_score != null ? t("strip.best", { score: d.best_score }) : null,
    t("strip.profile", { percent: d.profile_completeness }),
  ].filter(Boolean);

  return (
    <div>
      <p className="text-sm font-medium">{parts.join(" · ")}</p>
      <details className="mt-1" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
        <summary className="inline-flex min-h-11 cursor-pointer items-center rounded-sm text-sm font-medium text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
          {t("strip.numbers")}
        </summary>
        <div className="mt-2">{open ? <CandidateDashboard /> : null}</div>
      </details>
    </div>
  );
}
