"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

type Status = "registered" | "withdrawn" | "contacted";

const TONE: Record<Status, string> = {
  registered: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  contacted: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
  withdrawn: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
};

/** Which courses the learner has asked about, and where each stands. */
export function InterestList() {
  const t = useTranslations("courseInterest");
  const format = useFormatter();
  const { data, isPending, isError } = useQuery({
    queryKey: ["me", "course-interests"],
    queryFn: async () => {
      const { data, error } = await api.GET("/me/course-interests");
      if (error || !data) throw new Error("interests failed");
      return data;
    },
  });

  if (isPending) return <Skeleton className="mt-8 h-32 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;
  if (data.length === 0) {
    return (
      <div className="mt-8">
        <p className="text-sm text-muted">{t("empty")}</p>
        <ButtonLink href="/courses" className="mt-4">
          {t("emptyCta")}
        </ButtonLink>
      </div>
    );
  }

  return (
    <ul className="mt-8 space-y-4">
      {data.map((interest) => {
        const status = interest.status as Status;
        return (
          <li key={interest.id}>
            <Card>
              <CardBody>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    {/* The title the API resolved for this locale (ADR-041). */}
                    <Link
                      href={`/courses/${interest.course.slug}`}
                      className="text-base font-semibold hover:underline"
                    >
                      {interest.course.title}
                    </Link>
                    <p className="mt-0.5 text-sm text-muted">{interest.course.tenant.name}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold ${TONE[status]}`}
                  >
                    {t(`status.${status}`)}
                  </span>
                </div>
                <p className="mt-2 text-xs text-muted">
                  {t("registeredOn", {
                    date: format.dateTime(new Date(interest.registered_at), {
                      dateStyle: "medium",
                    }),
                  })}
                </p>
              </CardBody>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
