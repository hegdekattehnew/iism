"use client";

import { useFormatter, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { BATCH_INTEREST_LOOK } from "@/components/cards/batch-interest-look";
import { Alert, Card, CardBody } from "@/components/ui";
import { Avatar } from "@/components/ui/avatar";
import { CalendarIcon, MapPinIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import { Link } from "@/i18n/navigation";
import type { BatchInterest } from "@/lib/batches";
import { REPLY_WITHIN_DAYS, replyBy } from "@/lib/interest-reply";

/**
 * A batch the learner asked about (Sprint 100): the course and who runs it, where it stands as a
 * word, a shape and a tone, when it starts, and, while nobody has answered, the date a reply is
 * expected by (an ask, never a promise). A cancelled batch says so and why, in words: the learner
 * was told by notice, and this is where they come back to look. What the learner does next is a
 * `footer` the list passes in.
 */
export function BatchInterestCard({
  interest,
  footer,
}: {
  interest: BatchInterest;
  footer?: ReactNode;
}) {
  const t = useTranslations("batchInterest");
  const format = useFormatter();
  const b = interest.batch;
  const look = BATCH_INTEREST_LOOK[interest.status];
  const date = (value: string) =>
    format.dateTime(new Date(`${value}T00:00:00Z`), { dateStyle: "medium", timeZone: "UTC" });
  const place = [b.centre.location_district, b.centre.location_state].filter(Boolean).join(", ");
  const cancelled = b.phase === "cancelled";

  return (
    <Card>
      <CardBody className="p-4">
        <div className="flex items-start gap-3">
          <Avatar name={b.organisation.name} />
          <div className="min-w-0 flex-1">
            <Link
              href={`/courses/${b.course.slug}`}
              className="inline-flex min-h-11 items-center text-base font-semibold hover:underline"
            >
              {b.course.title}
            </Link>
            <p className="text-sm text-muted">
              {t("deliveredBy", { organisation: b.organisation.name, centre: b.centre.name })}
            </p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusChip tone={look.tone} icon={look.icon}>
            {t(`status.${interest.status}`)}
          </StatusChip>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm">
            <CalendarIcon className="h-4 w-4" />
            {t("starts", { date: date(b.starts_on) })}
          </span>
          {place && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm text-muted">
              <MapPinIcon className="h-4 w-4" />
              {place}
            </span>
          )}
        </div>
        {cancelled && (
          <Alert tone="warning" role={undefined} className="mt-3">
            {t(`cancelled.${b.cancel_reason ?? "by_organisation"}`)}
          </Alert>
        )}
        {interest.status === "registered" && !cancelled && (
          <div className="mt-3 text-sm">
            <p className="font-medium">
              {t("replyBy", { date: format.dateTime(replyBy(interest.registered_at), { dateStyle: "medium" }) })}
            </p>
            <p className="text-muted">{t("replyHelp", { days: REPLY_WITHIN_DAYS })}</p>
            <Link
              href="/contact"
              className="inline-flex min-h-11 items-center text-brand underline underline-offset-2"
            >
              {t("notHeard")}
            </Link>
          </div>
        )}
        {footer}
      </CardBody>
    </Card>
  );
}
