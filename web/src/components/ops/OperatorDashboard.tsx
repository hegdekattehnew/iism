"use client";

import { useTranslations } from "next-intl";

import { RankedBarList } from "@/components/charts/ranked-bar-list";
import { Skeleton, StatTile } from "@/components/ui";
import { useOperatorDashboard } from "@/lib/ops";

/**
 * An operator's first real landing screen (Sprint 39, BL-10.4).
 *
 * Sits above `VerificationQueue`, not instead of it -- the queue is still the
 * thing an operator acts on; this is the orientation `/admin` has never had.
 *
 * `scarce_skills` (Sprint 40) renders `market_scarce_skills()`'s own fields --
 * a read-only ranked list, since there is no skill-detail screen to drill
 * into yet.
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
  const scarce = data.scarce_skills ?? [];

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

      {scarce.length > 0 && (
        <>
          <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted">
            {t("scarceSkills")}
          </h3>
          <RankedBarList
            className="mt-3"
            emptyLabel={t("noScarceSkills")}
            items={scarce.map((s) => ({
              key: s.nos_code ?? s.name,
              label: s.name,
              value: s.required_by,
              secondary: t("scarceSecondary", { held: s.held_by }),
              tone: s.held_by === 0 ? "danger" : "warning",
            }))}
          />
        </>
      )}
    </div>
  );
}
