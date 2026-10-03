"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { GapPanel } from "@/components/GapPanel";
import { ReviewControl } from "@/components/ReviewControl";
import { ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { ApiError, readDetail } from "@/lib/http";

// From the generated client, never restated: a hand-written copy plus a cast
// let `completed`/`no_show` reach this screen with no colour and no compile error.
type Status = components["schemas"]["ApplicationOut"]["status"];

/** The Hindi title when there is one. Every other listing does this; these two
 *  did not, so /hi/applications showed English titles on a Hindi page. */
function useTitle() {
  return (job: { title: string }) =>
    job.title;
}

const TONE: Record<Status, string> = {
  applied: "bg-surface-muted text-foreground",
  shortlisted: "bg-success-surface text-success-text",
  hired: "bg-success-surface text-success-text",
  rejected: "bg-surface-muted text-muted",
  withdrawn: "bg-warning-surface text-warning-text",
  completed: "bg-success-surface text-success-text",
  no_show: "bg-warning-surface text-warning-text",
};

/** Where each application stands, in the candidate's own words. */
export function ApplicationList() {
  const t = useTranslations("applications");
  const format = useFormatter();
  const tr = useTranslations("reviews");
  const title = useTitle();
  const qc = useQueryClient();
  const [gapOpen, setGapOpen] = useState<string | null>(null);
  const { data, isPending, isError } = useQuery({
    queryKey: ["me", "applications"],
    queryFn: async () => {
      const { data, error } = await api.GET("/me/applications");
      if (error || !data) throw new Error("applications failed");
      return data;
    },
  });

  // The worker rating whoever posted the gig. The server fixes the direction.
  const ratePoster =
    (applicationId: string) =>
    async (review: { rating: number; comment: string | null }) => {
      const { error, response } = await api.POST("/me/applications/{application_id}/review", {
        params: { path: { application_id: applicationId } },
        body: review,
      });
      const code = response.status;
      if (error) throw new ApiError(code, readDetail(error));
    };

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
        const status: Status = application.status;
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
                {status === "rejected" && (
                  <div className="mt-3">
                    <button
                      type="button"
                      aria-expanded={gapOpen === application.id}
                      aria-controls={`gap-${application.id}`}
                      onClick={() => setGapOpen((cur) => (cur === application.id ? null : application.id))}
                      className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                    >
                      {gapOpen === application.id ? t("hideGap") : t("whyNotMe")}
                    </button>
                    {gapOpen === application.id && (
                      <div id={`gap-${application.id}`}>
                        <GapPanel applicationId={application.id} />
                      </div>
                    )}
                  </div>
                )}
                {status === "completed" &&
                  (application.reviewed ? (
                    <p className="mt-3 text-sm text-muted">{tr("givenPoster")}</p>
                  ) : (
                    <ReviewControl
                      prompt={tr("promptPoster", { organisation: application.job.tenant.name })}
                      submit={ratePoster(application.id)}
                      onSaved={() => qc.invalidateQueries({ queryKey: ["me", "applications"] })}
                    />
                  ))}
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
