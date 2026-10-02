"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { CoverageBar, LevelScale } from "@/components/CoverageBar";
import { ProgressRing } from "@/components/charts/progress-ring";
import { RankedBarList } from "@/components/charts/ranked-bar-list";
import { StatusFunnel } from "@/components/charts/status-funnel";
import { Skeleton, StatTile } from "@/components/ui";
import { useCandidateDashboard } from "@/lib/profile";

/**
 * A candidate's landing numbers (Sprint 39, BL-10.1) -- no aggregate of any of
 * this exists on `/matches` today; `MatchBrowser` renders one card per job
 * with no summary above it.
 *
 * The ring, the funnel and the top-matches bars (Sprint 40) render fields
 * `dashboard()` already returns -- `top_matches` is the same `scored` list
 * already computed for `match_count`/`best_score`, and a bar's drilldown
 * reuses `CoverageBar`/`LevelScale` rather than inventing a second gap view.
 */
export function CandidateDashboard() {
  const t = useTranslations("matchesPage.dashboard");
  const dashboard = useCandidateDashboard();
  const [expanded, setExpanded] = useState<string | null>(null);

  if (dashboard.isPending) {
    return <Skeleton className="h-16 w-full" />;
  }

  // Silent on error: `MatchBrowser` below already renders its own failure
  // state for the same underlying cause (a signed-out or refused caller).
  if (dashboard.isError) {
    return null;
  }

  const data = dashboard.data;
  const topMatches = data.top_matches ?? [];
  const expandedMatch = topMatches.find((m) => m.job_slug === expanded) ?? null;

  return (
    <div className="rounded-xl border border-border-token bg-surface p-5">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
        <StatTile value={data.match_count} label={t("liveMatches")} />
        <StatTile value={data.best_score ?? null} label={t("bestScore")} />
        <ProgressRing percent={data.profile_completeness} label={t("profileCompleteness")} />
      </div>

      <StatusFunnel
        className="mt-5"
        stages={[
          { key: "applied", label: t("applied"), value: data.applied },
          { key: "shortlisted", label: t("shortlisted"), value: data.shortlisted },
          { key: "hired", label: t("hired"), value: data.hired },
        ]}
      />

      {topMatches.length > 0 && (
        <>
          <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted">
            {t("topMatches")}
          </h3>
          <RankedBarList
            className="mt-3"
            selectedKey={expanded}
            emptyLabel={t("noMatches")}
            onSelect={(key) => setExpanded((current) => (current === key ? null : key))}
            items={topMatches.map((m) => ({
              key: m.job_slug,
              label: m.job_title,
              value: m.score,
              max: 100,
              tone: m.missing_mandatory > 0 ? "warning" : "brand",
            }))}
          />
          {expandedMatch && (
            <div
              id={`ranked-bar-panel-${expandedMatch.job_slug}`}
              className="mt-3 rounded-lg bg-surface-muted p-4"
            >
              <CoverageBar
                coverage={expandedMatch.coverage}
                missingMandatory={expandedMatch.missing_mandatory}
                capped={expandedMatch.capped_by_mandatory}
              />
              {expandedMatch.nsqf_level_min != null && (
                <LevelScale
                  required={expandedMatch.nsqf_level_min}
                  shortfall={expandedMatch.level_shortfall}
                />
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
