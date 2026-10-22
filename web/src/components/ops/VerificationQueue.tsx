"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Text } from "@/components/profile/fields";
import { Button, Card, CardBody, Skeleton } from "@/components/ui";
import { ChipRow, ChipSelect } from "@/components/ui/chip";
import { BookOpenIcon, BuildingIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import { Link } from "@/i18n/navigation";
import { NO_FILTERS, type QueueFilters, useVerificationQueue } from "@/lib/ops";

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
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<QueueFilters["kind"]>("");
  // The words are deferred so a keystroke does not start a request each; the kind is a choice.
  const deferredQ = useDeferredValue(q);
  const filtered = q.trim() !== "" || kind !== "";
  const queue = useVerificationQueue({ q: deferredQ, kind });

  // The filter row is there while the list loads, so nothing moves when the rows arrive
  // (ADR-065: a block above what people look at is the same shape before and after it loads).
  const filters = (
    <div className="mt-6 space-y-3">
      <label className="block text-sm">
        <span className="sr-only">{t("queueSearchLabel")}</span>
        <Text
          type="search"
          value={q}
          placeholder={t("queueSearchPlaceholder")}
          onChange={(event) => setQ(event.target.value)}
        />
      </label>
      <ChipRow label={t("queueFiltersLabel")}>
        <ChipSelect
          label={t("queueKindLabel")}
          active={kind !== ""}
          value={kind}
          onChange={(event) => setKind(event.target.value as QueueFilters["kind"])}
        >
          <option value="">{t("queueKindAll")}</option>
          <option value="employer">{t("employer")}</option>
          <option value="course_provider">{t("provider")}</option>
        </ChipSelect>
        {filtered && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setQ("");
              setKind(NO_FILTERS.kind);
            }}
          >
            {t("queueClear")}
          </Button>
        )}
      </ChipRow>
    </div>
  );

  if (queue.isPending) {
    return (
      <>
        {filters}
        <div className="mt-8 space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </>
    );
  }

  if (queue.isError) {
    return (
      <>
        {filters}
        <p className="mt-8 rounded-lg border border-danger-border bg-danger-surface p-4 text-sm text-danger-text">
          {t("queueFailed")}
        </p>
      </>
    );
  }

  const rows = (queue.data?.pages ?? []).flatMap((page) => page.items);
  // The queue's size, from the server. `rows.length` is only the pages loaded so far.
  const total = queue.data?.pages[0]?.total ?? 0;
  if (total === 0) {
    // An empty list and an answered queue look identical without this, and the
    // second is the one worth telling somebody about. A filter that matches nothing is a third.
    return (
      <>
        {filters}
        <p className="mt-8 text-muted">{filtered ? t("queueNoMatch") : t("queueEmpty")}</p>
      </>
    );
  }

  return (
    <>
      {filters}
      <p className="mt-4 text-muted" aria-busy={queue.isPlaceholderData}>
        {filtered
          ? rows.length < total
            ? t("queueFilteredShowing", { shown: rows.length, total })
            : t("queueFilteredCount", { count: total })
          : rows.length < total
            ? t("queueShowing", { shown: rows.length, total })
            : t("queueCount", { count: total })}
      </p>
      <ul className="mt-4 space-y-3">
        {rows.map((row) => (
          <li key={row.slug}>
            <Card>
              <CardBody>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link
                    href={`/admin/${row.slug}`}
                    className="inline-flex min-h-11 items-center text-lg font-semibold underline-offset-4 hover:underline"
                  >
                    {row.name}
                  </Link>
                  <StatusChip
                    tone={row.tenant_type === "employer" ? "brand" : "neutral"}
                    icon={row.tenant_type === "employer" ? BuildingIcon : BookOpenIcon}
                  >
                    {t(row.tenant_type === "employer" ? "employer" : "provider")}
                  </StatusChip>
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
      {queue.isFetchNextPageError && (
        <p className="mt-4 rounded-lg border border-danger-border bg-danger-surface p-4 text-sm text-danger-text">
          {t("queueMoreFailed")}
        </p>
      )}
      {queue.hasNextPage && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="secondary"
            disabled={queue.isFetchingNextPage}
            onClick={() => void queue.fetchNextPage()}
          >
            {t("queueMore", { left: total - rows.length })}
          </Button>
        </div>
      )}
    </>
  );
}
