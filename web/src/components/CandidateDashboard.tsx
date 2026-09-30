"use client";

import { useTranslations } from "next-intl";

import { Skeleton, StatTile } from "@/components/ui";
import { useCandidateDashboard } from "@/lib/profile";

/**
 * A candidate's landing numbers (Sprint 39, BL-10.1) -- no aggregate of any
 * of this exists on `/matches` today; `MatchBrowser` renders one card per job
 * with no summary above it.
 */
export function CandidateDashboard() {
  const t = useTranslations("matchesPage.dashboard");
  const dashboard = useCandidateDashboard();

  if (dashboard.isPending) {
    return <Skeleton className="h-16 w-full" />;
  }

  // Silent on error: `MatchBrowser` below already renders its own failure
  // state for the same underlying cause (a signed-out or refused caller).
  if (dashboard.isError) {
    return null;
  }

  const data = dashboard.data;

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-4 rounded-xl border border-border-token bg-surface p-5">
      <StatTile value={data.match_count} label={t("liveMatches")} />
      <StatTile value={data.best_score ?? null} label={t("bestScore")} />
      <StatTile value={data.applied} label={t("applied")} />
      <StatTile value={data.shortlisted} label={t("shortlisted")} />
      <StatTile value={data.hired} label={t("hired")} />
      <StatTile value={data.profile_completeness} label={t("profileCompleteness")} />
    </div>
  );
}
