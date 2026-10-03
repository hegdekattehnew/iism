"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { RankedBarList } from "@/components/charts/ranked-bar-list";
import { StatusFunnel } from "@/components/charts/status-funnel";
import { Skeleton, StatTile } from "@/components/ui";
import { useEmployerDashboard } from "@/lib/org";

/**
 * An employer's landing numbers (Sprint 39, BL-10.2) -- vacancies and
 * applicants aggregated across every posting, where every other screen here
 * shows exactly one job at a time.
 *
 * The funnel and the per-job bars (Sprint 40) render fields `dashboard()`
 * already returns -- `jobs` is the same `JobPoolOut` shape the workspace's own
 * job list computes, so expanding a bar costs no second request.
 */
export function EmployerDashboard({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("employerWorkspace.dashboard");
  const tr = useTranslations("reviews");
  const dashboard = useEmployerDashboard(orgSlug);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (dashboard.isPending) {
    return <Skeleton className="h-16 w-full" />;
  }

  // Silent on error: a real failure here (401, 403) is already shown by the
  // job list this section sits above, and a second error banner for the same
  // cause would just repeat it.
  if (dashboard.isError) {
    return null;
  }

  const data = dashboard.data;
  const jobs = data.jobs ?? [];
  const expandedJob = jobs.find((j) => j.job.slug === expanded) ?? null;

  return (
    <div className="rounded-xl border border-border-token bg-surface p-5">
      <div className="flex flex-wrap gap-x-8 gap-y-4">
        <StatTile value={data.posted_jobs} label={t("postedJobs")} />
        <StatTile value={data.open_jobs} label={t("openJobs")} />
        {/* Absent until a worker has rated this organisation, never a zero. */}
        {data.rating && (
          <StatTile
            value={data.rating.average}
            label={tr("asEmployer")}
            secondary={tr("count", { count: data.rating.count })}
          />
        )}
      </div>

      <StatusFunnel
        className="mt-5"
        stages={[
          { key: "applied", label: t("applied"), value: data.applied },
          { key: "shortlisted", label: t("shortlisted"), value: data.shortlisted },
          { key: "hired", label: t("hired"), value: data.hired },
        ]}
      />

      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted">
        {t("byVacancy")}
      </h3>
      <RankedBarList
        className="mt-3"
        selectedKey={expanded}
        emptyLabel={t("noVacancies")}
        onSelect={(key) => setExpanded((current) => (current === key ? null : key))}
        items={jobs.map((job) => ({
          key: job.job.slug,
          label: job.job.title,
          value: job.pool,
          tone: job.new_applications > 0 ? "warning" : "brand",
          secondary: t("poolSecondary", { ready: job.ready, new: job.new_applications }),
        }))}
      />
      {expandedJob && (
        <div
          id={`ranked-bar-panel-${expandedJob.job.slug}`}
          className="mt-3 flex flex-wrap gap-x-8 gap-y-3 rounded-lg bg-surface-muted p-4"
        >
          <StatTile value={expandedJob.pool} label={t("pool")} />
          <StatTile value={expandedJob.ready} label={t("ready")} />
          <StatTile value={expandedJob.nearly} label={t("nearly")} />
          <StatTile value={expandedJob.new_applications} label={t("newApplications")} />
        </div>
      )}
    </div>
  );
}
