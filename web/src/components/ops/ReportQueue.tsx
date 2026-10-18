"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  Skeleton,
} from "@/components/ui";
import { detailOf } from "@/lib/http";
import {
  NOTE_MAX,
  NOTE_MIN,
  type ListingReports,
  type QueueView,
  useDecideListing,
  useReportQueue,
} from "@/lib/moderation";
import { useMemberships } from "@/lib/org";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * Listings people have reported, and the ones an operator has removed (Sprint 59, ADR-069).
 *
 * **An operator decides about a listing, not a report**, so the queue is a list of listings with
 * what was said about each. A reporter is shown masked and the organisation's own words are never
 * mixed in. **Taking a listing down is the admin tier's alone**: a support operator is not offered
 * the control and then refused, it is simply absent (the server answers 403 either way).
 *
 * The reason typed for a takedown is **emailed to the organisation** -- the form says so, because
 * it is the one free-text field in the back office that leaves the building.
 */
export function ReportQueue() {
  const t = useTranslations("reportQueue");
  const [view, setView] = useState<QueueView>("open");
  const queue = useReportQueue(view);

  return (
    <section aria-labelledby="report-queue-heading">
      <h2
        id="report-queue-heading"
        className="text-2xl font-bold tracking-tight"
      >
        {t("title")}
      </h2>
      <p className="mt-2 text-muted">{t("subtitle")}</p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium" htmlFor="report-view">
          {t("view")}
        </label>
        <select
          id="report-view"
          value={view}
          onChange={(event) => setView(event.target.value as QueueView)}
          className="min-h-11 rounded-lg border border-input-border bg-background px-3 py-2 text-sm"
        >
          <option value="open">{t("viewOpen")}</option>
          <option value="taken_down">{t("viewTakenDown")}</option>
        </select>
        {queue.data && (
          <p className="text-sm tabular-nums text-muted">
            {t("counts", {
              open: queue.data.open_listings,
              removed: queue.data.taken_down,
            })}
          </p>
        )}
      </div>

      <Body queue={queue} view={view} />
    </section>
  );
}

function Body({
  queue,
  view,
}: {
  queue: ReturnType<typeof useReportQueue>;
  view: QueueView;
}) {
  const t = useTranslations("reportQueue");
  if (queue.isPending) {
    return (
      <div className="mt-6 space-y-3">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
    );
  }
  if (queue.isError) {
    return (
      <Alert role="alert" className="mt-6">
        {detailOf(queue.error) ?? t("failed")}
      </Alert>
    );
  }
  if (queue.data.items.length === 0) {
    return (
      <EmptyState title={t(view === "open" ? "emptyOpen" : "emptyRemoved")} className="mt-6" />
    );
  }
  return (
    <ul className="mt-6 space-y-3">
      {queue.data.items.map((item) => (
        <li key={`${item.target_type}-${item.target_id}`}>
          <Row item={item} />
        </li>
      ))}
    </ul>
  );
}

function Row({ item }: { item: ListingReports }) {
  const t = useTranslations("reportQueue");
  const format = useFormatter();
  const decide = useDecideListing();
  const me = useMemberships();
  const isAdmin = me.data?.staff_tier === "admin";
  const [note, setNote] = useState("");
  const removed = item.taken_down_at != null;
  const ready = note.trim().length >= NOTE_MIN;
  const act = (kind: "dismiss" | "takedown") =>
    decide.mutate(
      {
        target: item.target_type,
        id: item.target_id,
        ...(kind === "dismiss"
          ? { kind: "dismiss" as const, note: note.trim() }
          : { kind: "takedown" as const, reason: note.trim() }),
      },
      { onSuccess: () => setNote("") },
    );

  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-base font-semibold">{item.title}</span>
          <Badge>{t(`kind.${item.target_type}`)}</Badge>
          {removed && <Badge tone="bad">{t("removed")}</Badge>}
          {item.open_reports > 0 && (
            <Badge tone="warn">
              {t("reportsCount", { count: item.open_reports })}
            </Badge>
          )}
        </div>
        {item.organisation && (
          <p className="mt-1 text-xs text-muted">{item.organisation.name}</p>
        )}

        {Object.keys(item.reasons ?? {}).length > 0 && (
          <p className="mt-2 text-sm">
            {Object.entries(item.reasons ?? {})
              .map(([reason, count]) => `${t(`reason.${reason}`)} × ${count}`)
              .join(" · ")}
          </p>
        )}

        {(item.reports ?? []).length > 0 && (
          <ul className="mt-3">
            {(item.reports ?? []).map((report, index) => (
              <li
                key={index}
                className="border-t border-border-token py-2 text-sm first:border-t-0"
              >
                <p className="text-xs text-muted">
                  {t(`reason.${report.reason}`)}
                  {" · "}
                  {[report.reporter?.phone, report.reporter?.email]
                    .filter(Boolean)
                    .join(" · ") || t("noContact")}
                  {" · "}
                  {format.dateTime(new Date(report.created_at), {
                    dateStyle: "medium",
                  })}
                </p>
                {report.detail && (
                  <p className="mt-0.5 whitespace-pre-wrap">{report.detail}</p>
                )}
              </li>
            ))}
          </ul>
        )}

        {removed && (
          <p className="mt-3 text-sm">
            <span className="text-muted">{t("removedBecause")}: </span>
            {item.takedown_reason}
          </p>
        )}

        {removed ? (
          isAdmin && (
            <div className="mt-4">
              <Button
                variant="secondary"
                size="sm"
                disabled={decide.isPending}
                onClick={() =>
                  decide.mutate({
                    target: item.target_type,
                    id: item.target_id,
                    kind: "restore",
                  })
                }
              >
                {t("restore")}
              </Button>
            </div>
          )
        ) : (
          <div className="mt-4">
            <label
              className="block text-sm font-medium"
              htmlFor={`note-${item.target_id}`}
            >
              {t(isAdmin ? "noteLabelAdmin" : "noteLabel")}
            </label>
            <textarea
              id={`note-${item.target_id}`}
              name="note"
              rows={2}
              minLength={NOTE_MIN}
              maxLength={NOTE_MAX}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="mt-1 w-full rounded-lg border border-input-border bg-background px-3 py-2 text-sm"
            />
            {isAdmin && (
              <p className="mt-1 text-xs text-muted">{t("takedownHint")}</p>
            )}
            <div className="mt-3 flex flex-wrap gap-3">
              {item.open_reports > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!ready || decide.isPending}
                  onClick={() => act("dismiss")}
                >
                  {t("dismiss")}
                </Button>
              )}
              {isAdmin && (
                <Button
                  variant="danger"
                  size="sm"
                  disabled={!ready || decide.isPending}
                  onClick={() => act("takedown")}
                >
                  {t("takedown")}
                </Button>
              )}
            </div>
          </div>
        )}

        {decide.isError && (
          <Alert role="alert" className="mt-3">
            {detailOf(decide.error) ?? t("decideFailed")}
          </Alert>
        )}
      </CardBody>
    </Card>
  );
}
