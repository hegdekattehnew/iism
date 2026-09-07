"use client";

import { useTranslations } from "next-intl";

import { CoverageBar } from "@/components/CoverageBar";
import { Badge, Card, CardBody, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useOrgCandidates } from "@/lib/org";

/**
 * The authenticated shortlist: the same scorer, run the other way round.
 *
 * Identical payload to the demonstration console, including the part that
 * matters — **no candidate is identified**. Reference, headline, district,
 * years and the gap. Authentication changed who may look; it did not change
 * what there is to see.
 */
export function CandidateShortlist({
  orgSlug,
  jobSlug,
}: {
  orgSlug: string;
  jobSlug: string;
}) {
  const t = useTranslations("employerWorkspace");
  const te = useTranslations("employerConsole");
  const q = useOrgCandidates(orgSlug, jobSlug);

  if (q.isPending) {
    return (
      <ul className="space-y-3">
        {[0, 1, 2].map((i) => (
          <li key={i}>
            <Skeleton className="h-28 w-full rounded-xl" />
          </li>
        ))}
      </ul>
    );
  }
  if (q.isError) return <p className="text-sm text-muted">{t("noAccess")}</p>;

  const items = q.data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">{q.data?.job.title_en}</h2>
        <p className="mt-1 text-sm text-muted">
          {t("shortlistNote", { count: q.data?.total ?? 0 })}
        </p>
      </div>

      {items.length === 0 && (
        <p className="text-sm text-muted">{te("emptyPool")}</p>
      )}

      <ul className="space-y-3">
        {items.map((c) => {
          const missing = c.missing ?? [];
          const mandatoryGaps = missing.filter((m) => m.is_mandatory);
          return (
            <li key={c.reference}>
              <Card>
                <CardBody>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                        <span className="font-mono text-xs text-muted">
                          {c.reference}
                        </span>
                        {c.missing_mandatory === 0 ? (
                          <Badge tone="good">{te("ready")}</Badge>
                        ) : c.missing_mandatory === 1 ? (
                          <Badge tone="warn">{te("nearly")}</Badge>
                        ) : null}
                      </p>
                      <p className="mt-1 text-sm">{c.headline}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {[c.location_district, c.location_state]
                          .filter(Boolean)
                          .join(", ")}
                        {" · "}
                        {te("years", { years: c.years_experience })}
                      </p>
                    </div>
                    <span className="shrink-0 text-right">
                      <span className="text-lg font-bold tabular-nums">
                        {c.score}
                      </span>
                      <span className="text-xs text-muted">/100</span>
                    </span>
                  </div>

                  <div className="mt-3">
                    <CoverageBar
                      coverage={c.coverage}
                      missingMandatory={c.missing_mandatory}
                      capped={c.capped_by_mandatory}
                    />
                  </div>

                  {mandatoryGaps.length > 0 && (
                    <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">
                      {te("missingMandatory")}:{" "}
                      {mandatoryGaps.map((m) => m.name_en).join(" · ")}
                    </p>
                  )}
                </CardBody>
              </Card>
            </li>
          );
        })}
      </ul>

      <Link
        href={`/employer/${orgSlug}`}
        className="inline-block text-sm text-brand underline-offset-4 hover:underline"
      >
        {t("backToVacancies")}
      </Link>
    </div>
  );
}
