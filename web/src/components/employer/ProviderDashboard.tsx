"use client";

import { useTranslations } from "next-intl";

import { Skeleton, StatTile } from "@/components/ui";
import { useProviderDashboard } from "@/lib/org";

/**
 * A course provider's landing numbers (Sprint 39, BL-10.3) -- the direct
 * payoff of ADR-047's provider-reported `"enrolled"` status finally having a
 * screen, aggregated across every course rather than shown one at a time.
 */
export function ProviderDashboard({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("providerWorkspace.dashboard");
  const dashboard = useProviderDashboard(orgSlug);

  if (dashboard.isPending) {
    return <Skeleton className="h-16 w-full" />;
  }

  // Silent on error, the same reason the employer's own section is: a real
  // failure here is already shown by the course list this section sits above.
  if (dashboard.isError) {
    return null;
  }

  const data = dashboard.data;

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-4 rounded-xl border border-border-token bg-surface p-5">
      <StatTile value={data.published_courses} label={t("publishedCourses")} />
      <StatTile value={data.interested_live} label={t("interestedLive")} />
      <StatTile value={data.interested_total} label={t("interestedTotal")} />
      <StatTile value={data.enrolled} label={t("enrolled")} />
    </div>
  );
}
