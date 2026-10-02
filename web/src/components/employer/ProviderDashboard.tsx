"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { ProgressRing } from "@/components/charts/progress-ring";
import { RankedBarList } from "@/components/charts/ranked-bar-list";
import { Skeleton, StatTile } from "@/components/ui";
import { useProviderDashboard } from "@/lib/org";

/**
 * A course provider's landing numbers (Sprint 39, BL-10.3) -- the direct
 * payoff of ADR-047's provider-reported `"enrolled"` status finally having a
 * screen, aggregated across every course rather than shown one at a time.
 *
 * The ring and the per-course bars (Sprint 40) render fields
 * `provider_dashboard()` already returns -- `conversion_rate` is computed
 * server-side, never divided on the client, and `courses` is the same rows
 * `counts_by_course()` already fetched for the two totals above.
 */
export function ProviderDashboard({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("providerWorkspace.dashboard");
  const dashboard = useProviderDashboard(orgSlug);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (dashboard.isPending) {
    return <Skeleton className="h-16 w-full" />;
  }

  // Silent on error, the same reason the employer's own section is: a real
  // failure here is already shown by the course list this section sits above.
  if (dashboard.isError) {
    return null;
  }

  const data = dashboard.data;
  const courses = data.courses ?? [];
  const expandedCourse = courses.find((c) => c.course_slug === expanded) ?? null;

  return (
    <div className="rounded-xl border border-border-token bg-surface p-5">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
        <StatTile value={data.published_courses} label={t("publishedCourses")} />
        <StatTile value={data.interested_live} label={t("interestedLive")} />
        <StatTile value={data.interested_total} label={t("interestedTotal")} />
        <StatTile value={data.enrolled} label={t("enrolled")} />
        <ProgressRing percent={(data.conversion_rate ?? 0) * 100} label={t("conversionRate")} />
      </div>

      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted">
        {t("byCourse")}
      </h3>
      <RankedBarList
        className="mt-3"
        selectedKey={expanded}
        emptyLabel={t("noCourses")}
        onSelect={(key) => setExpanded((current) => (current === key ? null : key))}
        items={courses.map((course) => ({
          key: course.course_slug,
          label: course.course_title,
          value: course.total,
          secondary: t("interestSecondary", { live: course.live }),
        }))}
      />
      {expandedCourse && (
        <div
          id={`ranked-bar-panel-${expandedCourse.course_slug}`}
          className="mt-3 flex flex-wrap gap-x-8 gap-y-3 rounded-lg bg-surface-muted p-4"
        >
          <StatTile value={expandedCourse.live} label={t("interestedLive")} />
          <StatTile value={expandedCourse.total} label={t("interestedTotal")} />
        </div>
      )}
    </div>
  );
}
