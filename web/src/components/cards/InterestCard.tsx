"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Avatar } from "@/components/ui/avatar";
import { Card, CardBody } from "@/components/ui/card";
import { CalendarIcon } from "@/components/ui/icons";
import { INTEREST_LOOK, type InterestStatus } from "@/components/cards/interest-look";
import { StatusChip } from "@/components/ui/status-chip";
import { Link } from "@/i18n/navigation";
import type { components } from "@/lib/api-schema";

export { INTEREST_LOOK, type InterestStatus };
export type Interest = components["schemas"]["InterestOut"];

/** One course the learner asked about, on the same card as a vacancy or an application. */
export function InterestCard({ interest }: { interest: Interest }) {
  const t = useTranslations("courseInterest");
  const format = useFormatter();
  const look = INTEREST_LOOK[interest.status];
  const provider = interest.course.tenant.name;

  return (
    <Card>
      <CardBody className="p-4">
        <div className="flex items-start gap-3">
          <Avatar name={provider} />
          <div className="min-w-0 flex-1">
            {/* The title the API resolved for this locale (ADR-041). */}
            <Link href={`/courses/${interest.course.slug}`} className="text-base font-semibold hover:underline">
              {interest.course.title}
            </Link>
            <p className="text-sm text-muted">{provider}</p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusChip tone={look.tone} icon={look.icon}>
            {t(`status.${interest.status}`)}
          </StatusChip>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm text-muted">
            <CalendarIcon className="h-4 w-4" />
            {t("registeredOn", { date: format.dateTime(new Date(interest.registered_at), { dateStyle: "medium" }) })}
          </span>
        </div>
      </CardBody>
    </Card>
  );
}
