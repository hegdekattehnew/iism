"use client";

import { useTranslations } from "next-intl";

import { Skeleton, StatTile } from "@/components/ui";
import { useOperatorDashboard } from "@/lib/ops";

/**
 * An operator's first real landing screen (Sprint 39, BL-10.4).
 *
 * Sits above `VerificationQueue`, not instead of it -- the queue is still the
 * thing an operator acts on; this is the orientation `/admin` has never had.
 */
export function OperatorDashboard() {
  const t = useTranslations("ops.dashboard");
  const dashboard = useOperatorDashboard();

  if (dashboard.isPending) {
    return <Skeleton className="h-20 w-full" />;
  }

  if (dashboard.isError) {
    return <p className="text-sm text-danger-text">{t("failed")}</p>;
  }

  const data = dashboard.data;

  return (
    <div>
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <div className="mt-4 flex flex-wrap gap-x-8 gap-y-4">
        <StatTile value={data.unverified_organisations} label={t("unverifiedOrganisations")} />
        <StatTile value={data.unverified_certifications} label={t("unverifiedCertifications")} />
        <StatTile value={data.organisations} label={t("organisations")} />
        <StatTile value={data.candidates} label={t("candidates")} />
        <StatTile value={data.published_jobs} label={t("publishedJobs")} />
        <StatTile value={data.published_courses} label={t("publishedCourses")} />
      </div>
    </div>
  );
}
