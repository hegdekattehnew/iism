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

  if (dashboard.isError) {
    return <p className="text-sm text-danger-text">{t("failed")}</p>;
  }

  // **The same shape while it loads and after.** Sprint 73 put the verification queue straight under
  // this block (it used to sit two panels below, off screen), so a placeholder of a different height
  // moved a visible queue by 0.2 to 0.3 of the layout-shift budget. The heading and the tile labels
  // are static, a tile with no value draws its dash (`StatTile`), and the one variable-length part,
  // the scarce-skills list, is behind a row of fixed height that is there before and after.
  const data = dashboard.data;
  const scarce = data?.scarce_skills ?? [];
  const tile = (value: number | undefined, label: string) => (
    <StatTile value={value ?? null} label={label} />
  );

  return (
    <div>
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <div className="mt-4 flex flex-wrap gap-x-8 gap-y-4">
        {tile(data?.unverified_organisations, t("unverifiedOrganisations"))}
        {tile(data?.unverified_certifications, t("unverifiedCertifications"))}
        {tile(data?.organisations, t("organisations"))}
        {tile(data?.candidates, t("candidates"))}
        {tile(data?.published_jobs, t("publishedJobs"))}
        {tile(data?.published_courses, t("publishedCourses"))}
      </div>

      {data ? (
        <details className="group mt-6">
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 text-sm font-semibold tracking-wide text-muted uppercase [&::-webkit-details-marker]:hidden">
            {t("scarceSkills")}
            <span aria-hidden className="transition-transform group-open:rotate-90">
              ›
            </span>
          </summary>
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
        </details>
      ) : (
        <Skeleton className="mt-6 h-11 w-full" />
      )}
    </div>
  );
}
