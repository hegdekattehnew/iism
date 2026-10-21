"use client";

import { useFormatter, useTranslations } from "next-intl";

import { MessageForm } from "@/components/MessageForm";
import { GRIEVANCE_LOOK } from "@/components/cards/grievance-look";
import { Skeleton } from "@/components/ui";
import { StatusChip } from "@/components/ui/status-chip";
import { useIsSignedIn } from "@/lib/auth";
import { useMyGrievances } from "@/lib/grievances";


/**
 * `/grievance`: raise a grievance or ask something about your own data (Sprint 57, BL-14.3).
 *
 * For a signed-in person it also lists what they have already sent and where each stands, which is
 * the other half of "we acknowledge within 24 hours": a promise you can check. The operator's
 * note is never shown here -- it is the operator's evidence and may name other people.
 */
export function GrievanceForm() {
  const t = useTranslations("messageForm");
  return (
    <div className="space-y-10">
      <section aria-labelledby="grievance-form-heading">
        <h2 id="grievance-form-heading" className="text-xl font-semibold">
          {t("grievanceHeading")}
        </h2>
        <div className="mt-4">
          <MessageForm kinds={["grievance", "data_request"]} />
        </div>
      </section>
      <MyMessages />
    </div>
  );
}

function MyMessages() {
  const t = useTranslations("messageForm");
  const format = useFormatter();
  const signedIn = useIsSignedIn();
  const mine = useMyGrievances(signedIn);

  if (!signedIn) return null;
  if (mine.isPending) return <Skeleton className="h-24 w-full rounded-xl" />;
  if (mine.isError || mine.data.length === 0) return null;

  return (
    <section aria-labelledby="my-messages-heading">
      <h2 id="my-messages-heading" className="text-xl font-semibold">
        {t("mineHeading")}
      </h2>
      <ul className="mt-4">
        {mine.data.map((item) => (
          <li
            key={item.reference}
            className="border-t border-border-token py-3 first:border-t-0"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-semibold">
                {item.reference}
              </span>
              <StatusChip tone={GRIEVANCE_LOOK[item.status].tone} icon={GRIEVANCE_LOOK[item.status].icon}>
                {t(`status.${item.status}`)}
              </StatusChip>
              <span className="text-sm text-muted">
                {t(`kind.${item.kind}`)}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted">
              {t("sentOn", {
                date: format.dateTime(new Date(item.created_at), {
                  dateStyle: "medium",
                }),
              })}
              {item.resolved_at
                ? " · " +
                  t("closedOn", {
                    date: format.dateTime(new Date(item.resolved_at), {
                      dateStyle: "medium",
                    }),
                  })
                : ""}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
