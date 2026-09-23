"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Badge, Card, CardBody, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useVerificationQueue } from "@/lib/ops";

/**
 * Organisations waiting on a decision, oldest first.
 *
 * Oldest first because a queue that surfaces the newest arrival leaves its
 * oldest entry unanswered for ever -- and the counts are on the row because
 * verifying an employer with no vacancies and no members is verifying an
 * intention. What an organisation has actually *done* here is the cheapest
 * real signal available before anyone looks anything up.
 */
export function VerificationQueue() {
  const t = useTranslations("ops");
  const format = useFormatter();
  const queue = useVerificationQueue();

  if (queue.isPending) {
    return (
      <div className="mt-8 space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (queue.isError) {
    return (
      <p className="mt-8 rounded-lg border border-danger-border bg-danger-surface p-4 text-sm text-danger-text">
        {t("queueFailed")}
      </p>
    );
  }

  const rows = queue.data ?? [];
  if (rows.length === 0) {
    // An empty list and an answered queue look identical without this, and the
    // second is the one worth telling somebody about.
    return <p className="mt-8 text-muted">{t("queueEmpty")}</p>;
  }

  return (
    <>
      <p className="mt-2 text-muted">{t("queueCount", { count: rows.length })}</p>
      <ul className="mt-8 space-y-3">
        {rows.map((row) => (
          <li key={row.slug}>
            <Card>
              <CardBody>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link
                    href={`/admin/${row.slug}`}
                    className="text-lg font-semibold underline-offset-4 hover:underline"
                  >
                    {row.name}
                  </Link>
                  <Badge tone={row.tenant_type === "employer" ? "brand" : "neutral"}>
                    {t(row.tenant_type === "employer" ? "employer" : "provider")}
                  </Badge>
                </div>

                <p className="mt-1 text-sm text-muted">
                  {row.city ?? t("noCity")} ·{" "}
                  {t("registered", {
                    date: format.dateTime(new Date(row.created_at), {
                      dateStyle: "medium",
                    }),
                  })}
                </p>

                {/* What they have actually done here. An operator verifying an
                    organisation with nothing behind it is verifying nothing. */}
                <p className="mt-3 text-sm tabular-nums">
                  {t("activity", {
                    jobs: row.jobs,
                    courses: row.courses,
                    members: row.members,
                  })}
                </p>

                {row.website ? (
                  <p className="mt-1 truncate text-sm text-muted">{row.website}</p>
                ) : (
                  <p className="mt-1 text-sm text-muted">{t("noWebsite")}</p>
                )}
              </CardBody>
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}
