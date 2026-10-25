"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { BATCH_INTEREST_LOOK } from "@/components/cards/batch-interest-look";
import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Button, Skeleton } from "@/components/ui";
import { StatusChip } from "@/components/ui/status-chip";
import {
  useBatchLearners,
  useSetLearnerStatus,
  type Batch,
  type BatchLearner,
  type CentreStatus,
} from "@/lib/batches";
import { detailOf, isSignedOut } from "@/lib/http";
import { daysWaiting, isReplyOverdue } from "@/lib/interest-reply";

const TAKEN = ["enrolled", "attended"];

/**
 * The people who registered interest in one batch (Sprint 100, ADR-103, BL-18.7, BL-20.3), as the
 * centre that runs it and its organisation's owners and admins see them: the longest-waiting
 * unanswered first, how long they have waited (the same three-day rule the learner is shown), the
 * contact they chose to share, and one button per thing the centre may say: contacted, enrolled
 * (which takes a seat), attended (once it has started). **A learner who withdrew keeps the row and
 * loses the details**, and cannot be moved along. The server refuses the rest in its own words.
 */
export function BatchLearners({ org, batch }: { org: string; batch: Batch }) {
  const t = useTranslations("batchLearners");
  const format = useFormatter();
  const learners = useBatchLearners(org, batch.id);
  const set = useSetLearnerStatus(org, batch.id);
  const [now] = useState(() => Date.now());
  const started = batch.phase === "running" || batch.phase === "finished";
  const cancelled = batch.phase === "cancelled";

  if (learners.isPending) return <Skeleton className="h-24 w-full rounded-lg" />;
  if (isSignedOut(learners.error)) return <SessionExpired />;
  if (learners.isError) return <p className="text-sm text-muted">{t("noAccess")}</p>;
  const items = learners.data.items;
  if (items.length === 0) return <p className="text-sm text-muted">{t("none")}</p>;

  const act = (row: BatchLearner, status: CentreStatus) =>
    set.mutate({ interestId: row.interest_id, status });

  return (
    <div className="space-y-3">
      {set.error != null && (
        <Alert role="alert">{detailOf(set.error) ?? t("failed")}</Alert>
      )}
      <ul className="space-y-3">
        {items.map((row) => {
          const look = BATCH_INTEREST_LOOK[row.status];
          const live = row.status !== "withdrawn";
          const taken = TAKEN.includes(row.status);
          const name = row.contact?.full_name ?? t("someone");
          return (
            <li key={row.interest_id} className="rounded-lg border border-border-token p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="min-w-0 grow basis-40 text-sm font-medium">{name}</p>
                <StatusChip tone={look.tone} icon={look.icon}>
                  {t(`status.${row.status}`)}
                </StatusChip>
              </div>
              {live ? (
                <>
                  <p className="mt-1 break-words text-sm text-muted">
                    {[row.contact?.phone, row.contact?.email].filter(Boolean).join(" · ")}
                  </p>
                  {(row.location_district || row.location_state) && (
                    <p className="text-sm text-muted">
                      {[row.location_district, row.location_state].filter(Boolean).join(", ")}
                    </p>
                  )}
                  {row.message && <p className="mt-1 text-sm">{row.message}</p>}
                </>
              ) : (
                <p className="mt-1 text-sm text-muted">{t("withdrawnNote")}</p>
              )}
              <p
                className={
                  row.status === "registered" && isReplyOverdue(row.registered_at, now)
                    ? "mt-1 text-sm font-medium text-warning-text"
                    : "mt-1 text-sm text-muted"
                }
              >
                {t("registeredOn", {
                  date: format.dateTime(new Date(row.registered_at), { dateStyle: "medium" }),
                })}
                {row.status === "registered" &&
                  daysWaiting(row.registered_at, now) > 0 &&
                  ` · ${t("waiting", { days: daysWaiting(row.registered_at, now) })}`}
              </p>
              {live && !cancelled && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {row.status === "registered" && (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={set.isPending}
                      aria-label={t("contactedNamed", { name })}
                      onClick={() => act(row, "contacted")}
                    >
                      {t("contacted")}
                    </Button>
                  )}
                  {!taken && (
                    <Button
                      size="sm"
                      disabled={set.isPending}
                      aria-label={t("enrolledNamed", { name })}
                      onClick={() => act(row, "enrolled")}
                    >
                      {t("enrolled")}
                    </Button>
                  )}
                  {row.status === "enrolled" && started && (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={set.isPending}
                      aria-label={t("attendedNamed", { name })}
                      onClick={() => act(row, "attended")}
                    >
                      {t("attended")}
                    </Button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
