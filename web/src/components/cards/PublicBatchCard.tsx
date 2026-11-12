"use client";

import { useFormatter, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Card, CardBody } from "@/components/ui";
import { Avatar } from "@/components/ui/avatar";
import {
  CalendarIcon,
  MapPinIcon,
  NavigationIcon,
  RupeeIcon,
  ShieldCheckIcon,
  UsersIcon,
} from "@/components/ui/icons";
import { Link } from "@/i18n/navigation";
import type { PublicBatch } from "@/lib/batches";

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

function Mark({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 text-success-text">
      <ShieldCheckIcon className="h-4 w-4" />
      {children}
    </span>
  );
}

/**
 * One batch as a learner sees it (Sprint 100, ADR-103, BL-20.2): the course and **who runs it**, how
 * far it is, when it starts, what is left and what it costs. "Course by X, delivered by Y at Z" with
 * each organisation's own mark and the centre's own, and a card **never says "not verified"**. How
 * near it is says what it says and nothing more: an unknown place reads as nothing at all, and a
 * batch far away is labelled, never hidden. The fee is the centre's own figure when it set one.
 *
 * What the learner does next is a `footer` the list passes in (register, or take it back).
 */
export function PublicBatchCard({ batch: b, footer }: { batch: PublicBatch; footer?: ReactNode }) {
  const t = useTranslations("publicBatches");
  const format = useFormatter();
  const date = (value: string) =>
    format.dateTime(new Date(`${value}T00:00:00Z`), { dateStyle: "medium", timeZone: "UTC" });
  const place = [b.centre.location_district, b.centre.location_state].filter(Boolean).join(", ");
  const fee = b.fee_effective;
  const full = b.phase === "full";

  return (
    <Card>
      <CardBody>
        <div className="flex items-start gap-3">
          <Avatar name={b.organisation.name} />
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold">
              <Link
                href={`/courses/${b.course.slug}`}
                className="inline-flex min-h-11 items-center hover:underline"
              >
                {b.course.title}
              </Link>
            </h3>
            {b.label && <p className="text-sm text-muted">{b.label}</p>}
            <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
              <span>{t("courseBy", { organisation: b.course.provider.name })}</span>
              {b.course.provider.is_verified && <Mark>{t("reviewed")}</Mark>}
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
          {b.reach !== "unknown" && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-accent-soft px-2.5 py-1 text-sm font-medium text-brand">
              <NavigationIcon className="h-4 w-4" />
              {t(`reach.${b.reach}`)}
            </span>
          )}
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm">
            <UsersIcon className="h-4 w-4" />
            {full ? t("full") : t("seatsLeft", { left: b.seats_left, seats: b.seats })}
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
        {footer}
      </CardBody>
    </Card>
  );
}
