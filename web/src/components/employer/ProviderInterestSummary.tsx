"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Badge, Card, CardBody, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

/**
 * A provider's landing surface: which of their courses people want.
 *
 * An employer reaches their applicants through a vacancy, so they need no
 * equivalent. A provider has no vacancies to go through, which is why this
 * exists and why `ORG_NAV` gives them a second nav item.
 */
export function ProviderInterestSummary({ org }: { org: string }) {
  const t = useTranslations("providerInbox");
  const { data, isPending, isError } = useQuery({
    queryKey: ["org", org, "interests"],
    queryFn: async () => {
      const { data, error } = await api.GET("/org/{org_slug}/interests", {
        params: { path: { org_slug: org } },
      });
      if (error || !data) throw new Error("summary failed");
      return data;
    },
  });

  if (isPending) return <Skeleton className="mt-8 h-32 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;
  if (data.length === 0) return <p className="mt-8 text-sm text-muted">{t("noCourses")}</p>;

  return (
    <ul className="mt-8 space-y-3">
      {data.map((row) => (
        <li key={row.course_slug}>
          <Card>
            <CardBody>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Link
                  href={`/employer/${org}/courses/${row.course_slug}/interests`}
                  className="text-base font-semibold hover:underline"
                >
                  {row.course_title}
                </Link>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge tone={row.live > 0 ? "good" : undefined}>
                    {t("liveCount", { count: row.live })}
                  </Badge>
                  {row.total > row.live && (
                    <span className="text-xs text-muted">
                      {t("totalEver", { count: row.total })}
                    </span>
                  )}
                </div>
              </div>
            </CardBody>
          </Card>
        </li>
      ))}
    </ul>
  );
}
