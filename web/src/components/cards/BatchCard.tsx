"use client";

import { useFormatter, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { BATCH_LOOK } from "@/components/cards/batch-look";
import { Alert, Card, CardBody } from "@/components/ui";
import { Avatar } from "@/components/ui/avatar";
import { CalendarIcon, MapPinIcon, RupeeIcon, ShieldCheckIcon, UsersIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import type { Batch } from "@/lib/batches";

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

/** A small "reviewed" mark: a shape and words, never colour alone. */
function Mark({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 text-success-text">
      <ShieldCheckIcon className="h-4 w-4" />
      {children}
    </span>
  );
}

/**
 * One batch: **"Course by X, delivered by Y at Z"** (Sprint 98, ADR-103). A course and the people who
 * teach it are not always the same organisation, so both are named with their own marks: the
 * organisation's ("Reviewed by our team") is a statement about the organisation, the centre's
 * ("Address checked") is a separate one about its place, and a card never says "not verified" of
 * either (an absent mark in a list reads as a charge). The fee is the centre's own figure when it set
 * one, and says so.
 *
 * What a person does with it next is a `footer` the list passes in, so the same card serves the
 * organisation's list (publish, cancel) and, in Sprint 100, a learner's.
 */
export function BatchCard({ batch: b, footer }: { batch: Batch; footer?: ReactNode }) {
  const t = useTranslations("batches");
  const format = useFormatter();
  const look = BATCH_LOOK[b.phase];
  const date = (value: string) =>
    format.dateTime(new Date(`${value}T00:00:00Z`), { dateStyle: "medium", timeZone: "UTC" });
  const place = [b.centre.location_district, b.centre.location_state].filter(Boolean).join(", ");
  const fee = b.fee_effective;
  const live = b.phase === "draft" || b.phase === "open" || b.phase === "full";

  return (
    <Card>
      <CardBody>
        <div className="flex items-start gap-3">
          <Avatar name={b.organisation.name} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h3 className="min-w-0 grow basis-48 text-base font-semibold">{b.course.title}</h3>
              <StatusChip tone={look.tone} icon={look.icon}>
                {t(`phase.${b.phase}`)}
              </StatusChip>
            </div>
            {b.label && <p className="text-sm text-muted">{b.label}</p>}
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
              <span>
                {b.course.own
                  ? t("ownCourse")
                  : t("courseBy", { organisation: b.course.provider.name })}
              </span>
              {!b.course.own && b.course.provider.is_verified && <Mark>{t("reviewed")}</Mark>}
            </p>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
              <span>{t("deliveredBy", { organisation: b.organisation.name, centre: b.centre.name })}</span>
              {b.organisation.is_verified && <Mark>{t("reviewed")}</Mark>}
              {b.centre.is_verified && <Mark>{t("addressChecked")}</Mark>}
            </p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm">
            <CalendarIcon className="h-4 w-4" />
            {t("dates", { start: date(b.starts_on), end: date(b.ends_on) })}
          </span>
          {place && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm text-muted">
              <MapPinIcon className="h-4 w-4" />
              {place}
            </span>
          )}
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm">
            <UsersIcon className="h-4 w-4" />
            {b.phase === "draft" || b.phase === "cancelled"
              ? t("seatsTotal", { seats: b.seats })
              : t("seatsLeft", { left: b.seats_left, seats: b.seats })}
          </span>
          {fee != null && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-accent-soft px-2.5 py-1 text-sm font-semibold text-brand">
              <RupeeIcon className="h-4 w-4" />
              {fee === 0 ? t("feeFree") : t("fee", { amount: inr(fee) })}
            </span>
          )}
        </div>
        <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
          <span className="rounded-md bg-accent-soft px-2 py-0.5 text-xs font-semibold text-brand">
            {t(`mode.${b.mode}`)}
          </span>
          {b.fee_is_override && <span>{t("feeSetByCentre")}</span>}
          {b.schedule && <span>{b.schedule}</span>}
        </p>

        <p className="mt-2 text-sm text-muted">
          {b.phase === "cancelled" && b.cancel_reason
            ? t(`story.cancelled.${b.cancel_reason}`)
            : t(`story.${b.phase}`)}
        </p>
        {live && !b.course.available && (
          <Alert tone="warning" role={undefined} className="mt-3">
            {t("courseUnavailable")}
          </Alert>
        )}
        {footer}
      </CardBody>
    </Card>
  );
}
