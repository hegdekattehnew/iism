"use client";

import { useTranslations } from "next-intl";

import { Skeleton, StatTile } from "@/components/ui";
import { useEmployerDashboard } from "@/lib/org";

/**
 * An employer's landing numbers (Sprint 39, BL-10.2) -- vacancies and
 * applicants aggregated across every posting, where every other screen here
 * shows exactly one job at a time.
 */
export function EmployerDashboard({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("employerWorkspace.dashboard");
  const dashboard = useEmployerDashboard(orgSlug);

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

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-4 rounded-xl border border-border-token bg-surface p-5">
      <StatTile value={data.posted_jobs} label={t("postedJobs")} />
      <StatTile value={data.open_jobs} label={t("openJobs")} />
      <StatTile value={data.applied} label={t("applied")} />
      <StatTile value={data.shortlisted} label={t("shortlisted")} />
      <StatTile value={data.hired} label={t("hired")} />
    </div>
  );
}
