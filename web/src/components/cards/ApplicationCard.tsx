"use client";

import { useFormatter, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { CalendarIcon, ClockIcon } from "@/components/ui/icons";
import { APPLICATION_LOOK, type ApplicationStatus } from "@/components/cards/application-look";
import { StatusChip } from "@/components/ui/status-chip";
import { Link } from "@/i18n/navigation";
import type { components } from "@/lib/api-schema";

export { APPLICATION_LOOK, type ApplicationStatus };
export type Application = components["schemas"]["ApplicationOut"];

/**
 * One application on the list, on the same card as a vacancy (Sprint 87, BL-19.17): the employer's
 * mark, the title and employer, **the state as a chip with a shape**, the date as an icon chip, the
 * sentence that says what the state means, and the employer's own message set apart. What a person
 * does next (why not me, rating the poster) is the list's business and arrives as `footer`.
 */
export function ApplicationCard({ application, footer }: { application: Application; footer?: ReactNode }) {
  const t = useTranslations("applications");
  const format = useFormatter();
  const status = application.status;
  const look = APPLICATION_LOOK[status];
  const employer = application.job.tenant.name;

  return (
    <Card>
      <CardBody className="p-4">
        <div className="flex items-start gap-3">
          <Avatar name={employer} />
          <div className="min-w-0 flex-1">
            {application.job.removed ? (
              // Removed by an operator: the page is gone, so there is nothing to link to.
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-base font-semibold">{application.job.title}</span>
                <Badge tone="bad">{t("removed")}</Badge>
              </span>
            ) : (
              <Link href={`/jobs/${application.job.slug}`} className="text-base font-semibold hover:underline">
                {application.job.title}
              </Link>
            )}
            <p className="text-sm text-muted">{employer}</p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <StatusChip tone={look.tone} icon={look.icon}>
            {t(`status.${status}`)}
          </StatusChip>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm text-muted">
            <CalendarIcon className="h-4 w-4" />
            {t("appliedOn", { date: format.dateTime(new Date(application.applied_at), { dateStyle: "medium" }) })}
          </span>
        </div>

        <p className="mt-2 text-sm text-muted">{t(`statusHint.${status}`)}</p>

        {application.status_message && (
          <div className="mt-3 rounded-lg border border-border-token bg-surface-muted px-3 py-2">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
              <ClockIcon className="h-3.5 w-3.5" />
              <span>
                {t("fromEmployer", { organisation: employer })}
                {application.status_message_at &&
                  ` · ${format.dateTime(new Date(application.status_message_at), { dateStyle: "medium" })}`}
              </span>
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm">{application.status_message}</p>
          </div>
        )}

        {footer}
      </CardBody>
    </Card>
  );
}
