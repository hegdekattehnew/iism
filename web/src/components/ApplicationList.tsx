"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { ApplicationCard } from "@/components/cards/ApplicationCard";
import { SavedJobRow } from "@/components/cards/SavedJobRow";
import { GapPanel } from "@/components/GapPanel";
import { ReviewControl } from "@/components/ReviewControl";
import { ButtonLink, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { apiErrorFrom } from "@/lib/http";
import { EmptyState } from "@/components/ui/empty-state";
import { BookmarkIcon, BriefcaseIcon } from "@/components/ui/icons";

/** Where each application stands, in the candidate's own words. */
export function ApplicationList() {
  const t = useTranslations("applications");
  const tr = useTranslations("reviews");
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
      if (error) throw apiErrorFrom(code, error);
    };

  if (isPending) return <Skeleton className="mt-8 h-32 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;
  if (data.length === 0) {
    return (
      <EmptyState
        icon={BriefcaseIcon}
        title={t("empty")}
        action={<ButtonLink href="/matches">{t("emptyCta")}</ButtonLink>}
        className="mt-8"
      />
    );
  }

  return (
    <ul className="mt-8 space-y-4">
      {data.map((application) => {
        const status = application.status;
        return (
          <li key={application.id}>
            <ApplicationCard
              application={application}
              footer={
                <>
                  {status === "rejected" && (
                    <div className="mt-3">
                      <button
                        type="button"
                        aria-expanded={gapOpen === application.id}
                        aria-controls={`gap-${application.id}`}
                        onClick={() => setGapOpen((cur) => (cur === application.id ? null : application.id))}
                        className="inline-flex min-h-11 items-center rounded-lg text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
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
                </>
              }
            />
          </li>
        );
      })}
    </ul>
  );
}

/** Bookmarks. Saving tells the employer nothing, and this page says so. */
export function SavedList() {
  const t = useTranslations("applications");
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
      <EmptyState
        icon={BookmarkIcon}
        title={t("savedEmpty")}
        action={<ButtonLink href="/jobs">{t("emptyCta")}</ButtonLink>}
        className="mt-8"
      />
    );
  }

  return (
    <ul className="mt-8 space-y-3">
      {data.map((row) => (
        <li key={row.job.slug}>
          <SavedJobRow slug={row.job.slug} title={row.job.title} employer={row.job.tenant.name} />
        </li>
      ))}
    </ul>
  );
}
