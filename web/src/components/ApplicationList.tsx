"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useLocale, useTranslations } from "next-intl";

import { ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

type Status = "applied" | "withdrawn" | "shortlisted" | "rejected" | "hired";

/** The Hindi title when there is one. Every other listing does this; these two
 *  did not, so /hi/applications showed English titles on a Hindi page. */
function useTitle() {
  const isHi = useLocale() === "hi";
  return (job: { title_en: string; title_hi?: string | null }) =>
    isHi && job.title_hi ? job.title_hi : job.title_en;
}

const TONE: Record<Status, string> = {
  applied: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  shortlisted: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
  hired: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
  rejected: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  withdrawn: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
};

/** Where each application stands, in the candidate's own words. */
export function ApplicationList() {
  const t = useTranslations("applications");
  const format = useFormatter();
  const title = useTitle();
  const { data, isPending, isError } = useQuery({
    queryKey: ["me", "applications"],
    queryFn: async () => {
      const { data, error } = await api.GET("/me/applications");
      if (error || !data) throw new Error("applications failed");
      return data;
    },
  });

  if (isPending) return <Skeleton className="mt-8 h-32 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;
  if (data.length === 0) {
    return (
      <div className="mt-8">
        <p className="text-sm text-muted">{t("empty")}</p>
        <ButtonLink href="/matches" className="mt-4">
          {t("emptyCta")}
        </ButtonLink>
      </div>
    );
  }

  return (
    <ul className="mt-8 space-y-4">
      {data.map((application) => {
        const status = application.status as Status;
        return (
          <li key={application.id}>
            <Card>
              <CardBody>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link
                      href={`/jobs/${application.job.slug}`}
                      className="text-base font-semibold hover:underline"
                    >
                      {title(application.job)}
                    </Link>
                    <p className="text-sm text-muted">{application.job.tenant.name}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-lg px-2.5 py-1 text-sm font-semibold ${TONE[status]}`}
                  >
                    {t(`status.${status}`)}
                  </span>
                </div>
                <p className="mt-2 text-sm text-muted">{t(`statusHint.${status}`)}</p>
                <p className="mt-1 text-xs text-muted">
                  {t("appliedOn", {
                    date: format.dateTime(new Date(application.applied_at), {
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

/** Bookmarks. Saving tells the employer nothing, and this page says so. */
export function SavedList() {
  const t = useTranslations("applications");
  const title = useTitle();
  const { data, isPending, isError } = useQuery({
    queryKey: ["me", "saved-jobs"],
    queryFn: async () => {
      const { data, error } = await api.GET("/me/saved-jobs");
      if (error || !data) throw new Error("saved failed");
      return data;
    },
  });

  if (isPending) return <Skeleton className="mt-8 h-24 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;
  if (data.length === 0) {
    return (
      <div className="mt-8">
        <p className="text-sm text-muted">{t("savedEmpty")}</p>
        <ButtonLink href="/jobs" className="mt-4">
          {t("emptyCta")}
        </ButtonLink>
      </div>
    );
  }

  return (
    <ul className="mt-8 space-y-3">
      {data.map((row) => (
        <li key={row.job.slug}>
          <Card>
            <CardBody>
              <Link
                href={`/jobs/${row.job.slug}`}
                className="text-base font-semibold hover:underline"
              >
                {title(row.job)}
              </Link>
              <p className="text-sm text-muted">{row.job.tenant.name}</p>
            </CardBody>
          </Card>
        </li>
      ))}
    </ul>
  );
}
