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
import {
  NOTE_MAX,
  NOTE_MIN,
  type GrievanceStatus,
  type QueueItem,
  useDecideGrievance,
  useGrievanceQueue,
} from "@/lib/grievances";
import { detailOf } from "@/lib/http";

const TONE: Record<GrievanceStatus, "warn" | "brand" | "good" | "neutral"> = {
  open: "warn",
  acknowledged: "brand",
  resolved: "good",
  dismissed: "neutral",
};

type Filter = GrievanceStatus | "all";
const FILTERS: Filter[] = [
  "open",
  "acknowledged",
  "resolved",
  "dismissed",
  "all",
];

/**
 * Messages people have sent us, the ones owed an answer first (Sprint 57, BL-14.3, ADR-067).
 *
 * **The default view is everything, not "waiting".** A message that has been acknowledged is still
 * owed a resolution within 15 days, so a default that showed only the unacknowledged ones would
 * drop it from sight the moment somebody pressed the first button. The server orders the ones
 * owed an answer first, so nothing is lost by not narrowing.
 *
 * **Overdue is measured against what the grievance page promises** (24 hours to acknowledge, 15
 * days to resolve), and the numbers come from the server's settings, so this screen cannot drift
 * from the page. A contact message promises nothing and is never overdue.
 *
 * **The account is masked, the message and the reply address are not**: an operator cannot answer
 * a person without them, and cannot do anything with a full phone number that a masked one and
 * the reference do not already let them do. We never write to the address ourselves -- the
 * operator replies from the grievance officer's own mailbox.
 */
export function GrievanceQueue() {
  const t = useTranslations("grievanceQueue");
  const [filter, setFilter] = useState<Filter>("all");
  const queue = useGrievanceQueue(filter);

  return (
    <section aria-labelledby="grievance-queue-heading">
      <h2
        id="grievance-queue-heading"
        className="text-2xl font-bold tracking-tight"
      >
        {t("title")}
      </h2>
      <p className="mt-2 text-muted">{t("subtitle")}</p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium" htmlFor="grievance-filter">
          {t("filter")}
        </label>
        <select
          id="grievance-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value as Filter)}
          className="rounded-lg border border-input-border bg-background px-3 py-2 text-sm"
        >
          {FILTERS.map((value) => (
            <option key={value} value={value}>
              {t(`filters.${value}`)}
            </option>
          ))}
        </select>
        {queue.data && (
          <p className="text-sm tabular-nums text-muted">
            {t("counts", {
              open: queue.data.open,
              overdue: queue.data.overdue,
            })}
          </p>
        )}
      </div>

      <Body queue={queue} />
    </section>
  );
}

function Body({ queue }: { queue: ReturnType<typeof useGrievanceQueue> }) {
  const t = useTranslations("grievanceQueue");

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
    return <p className="mt-6 text-muted">{t("empty")}</p>;
  }
  return (
    <ul className="mt-6 space-y-3">
      {queue.data.items.map((item) => (
        <li key={item.id}>
          <Row item={item} />
        </li>
      ))}
    </ul>
  );
}

function Row({ item }: { item: QueueItem }) {
  const t = useTranslations("grievanceQueue");
  const format = useFormatter();
  const decide = useDecideGrievance();
  const [note, setNote] = useState("");
  const closed = item.status === "resolved" || item.status === "dismissed";
  const ready = note.trim().length >= NOTE_MIN;
  const date = (value: string) =>
    format.dateTime(new Date(value), { dateStyle: "medium" });

  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-semibold">
            {item.reference}
          </span>
          <Badge tone={TONE[item.status]}>{t(`status.${item.status}`)}</Badge>
          <Badge>{t(`kind.${item.kind}`)}</Badge>
          {item.overdue_acknowledge && (
            <Badge tone="bad">{t("overdueAcknowledge")}</Badge>
          )}
          {item.overdue_resolve && (
            <Badge tone="bad">{t("overdueResolve")}</Badge>
          )}
        </div>

        <p className="mt-1 text-xs text-muted">
          {t("received", { date: date(item.created_at) })}
          {item.acknowledged_at
            ? ` · ${t("acknowledgedOn", { date: date(item.acknowledged_at) })}`
            : ""}
          {item.resolved_at
            ? ` · ${t("closedOn", { date: date(item.resolved_at) })}`
            : ""}
        </p>

        <p className="mt-3 whitespace-pre-wrap break-words text-sm">
          {item.body}
        </p>

        <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
          {item.reply_to ? (
            <>
              <dt className="text-muted">{t("replyTo")}</dt>
              <dd className="break-all">{item.reply_to}</dd>
            </>
          ) : item.account ? (
            <>
              <dt className="text-muted">{t("account")}</dt>
              <dd className="break-all">
                {[item.account.phone, item.account.email]
                  .filter(Boolean)
                  .join(" · ") || t("noContact")}
              </dd>
            </>
          ) : null}
        </dl>

        {closed ? (
          item.resolution_note && (
            <p className="mt-3 text-sm">
              <span className="text-muted">{t("note")}: </span>
              {item.resolution_note}
            </p>
          )
        ) : (
          <div className="mt-4">
            <label
              className="block text-sm font-medium"
              htmlFor={`note-${item.id}`}
            >
              {t("noteLabel")}
            </label>
            <textarea
              id={`note-${item.id}`}
              name="note"
              rows={2}
              minLength={NOTE_MIN}
              maxLength={NOTE_MAX}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder={t("notePlaceholder")}
              className="mt-1 w-full rounded-lg border border-input-border bg-background px-3 py-2 text-sm"
            />
            <div className="mt-3 flex flex-wrap gap-3">
              {item.status === "open" && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={decide.isPending}
                  onClick={() =>
                    decide.mutate({ id: item.id, decision: "acknowledge" })
                  }
                >
                  {t("acknowledge")}
                </Button>
              )}
              <Button
                size="sm"
                disabled={!ready || decide.isPending}
                onClick={() =>
                  decide.mutate({
                    id: item.id,
                    decision: "resolve",
                    note: note.trim(),
                  })
                }
              >
                {t("resolve")}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={!ready || decide.isPending}
                onClick={() =>
                  decide.mutate({
                    id: item.id,
                    decision: "dismiss",
                    note: note.trim(),
                  })
                }
              >
                {t("dismiss")}
              </Button>
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
