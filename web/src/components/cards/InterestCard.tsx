"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Avatar } from "@/components/ui/avatar";
import { Card, CardBody } from "@/components/ui/card";
import { AwardIcon, CalendarIcon, CheckIcon, ClockIcon, XCircleIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import { Link } from "@/i18n/navigation";
import type { components } from "@/lib/api-schema";

// From the generated client, never restated: a hand-written three-value copy let `enrolled` reach this
// screen with no colour and no wording, so a learner who had been enrolled saw a raw message key.
export type InterestStatus = components["schemas"]["InterestOut"]["status"];
export type Interest = components["schemas"]["InterestOut"];

type Look = { tone: "neutral" | "good" | "warn"; icon: typeof ClockIcon };

/** A shape and a tone for every state a provider can set (typed by `Record`: a new one fails to compile). */
export const INTEREST_LOOK: Record<InterestStatus, Look> = {
  registered: { tone: "neutral", icon: ClockIcon },
  contacted: { tone: "good", icon: CheckIcon },
  enrolled: { tone: "good", icon: AwardIcon },
  withdrawn: { tone: "warn", icon: XCircleIcon },
};

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
