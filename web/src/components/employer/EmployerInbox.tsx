"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { CoverageBar } from "@/components/CoverageBar";
import { ApplicantNotes } from "@/components/employer/ApplicantNotes";
import { ReviewControl } from "@/components/ReviewControl";
import { APPLICATION_LOOK } from "@/components/cards/application-look";
import { Badge, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { InboxIcon, TargetIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { employerDashboardKey, invalidatePublicCounts } from "@/lib/counts";
import { saveCsv } from "@/lib/download";
import { apiErrorFrom, detailOf } from "@/lib/http";
import { STATUS_MESSAGE_MAX } from "@/lib/hiring";
import { EmptyState } from "@/components/ui/empty-state";
import { UsersIcon } from "@/components/ui/icons";

// Derived from the generated schema, never restated: the hand-written
// three-value union this replaced is why `completed` and `no_show` could not
// be set from here at all.
type EmployerStatus = components["schemas"]["StatusIn"]["status"];

// A finished gig is final. The server refuses any further move, so the card
// offers none.
const ENDED = ["completed", "no_show"];

/**
 * Who applied, and how to reach them.
 *
 * **Contact details appear here and nowhere else in the employer surface.**
 * They are present because the candidate applied, and absent the moment they
 * withdraw — the row stays so the employer's own history is not rewritten, and
 * `contact` comes back null. The card beside it is the same de-identified
 * payload the ranked pool shows.
 */
export function EmployerInbox({ org, jobSlug }: { org: string; jobSlug: string }) {
  const t = useTranslations("employerInbox");
  const tr = useTranslations("reviews");
  const tc = useTranslations("employerConsole");
  const format = useFormatter();
  const qc = useQueryClient();

  const key = ["org", org, "applications", jobSlug];
  const { data, isPending, isError } = useQuery({
    queryKey: key,
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/org/{org_slug}/jobs/{job_slug}/applications",
        { params: { path: { org_slug: org, job_slug: jobSlug } } },
      );
      if (error || !data) throw new Error("inbox failed");
      return data;
    },
  });

  // What the employer has typed for each applicant and not yet sent (Sprint 60). It goes with the
  // next status button they press, and is cleared once it has been sent.
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const exportCsv = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.GET(
        "/org/{org_slug}/jobs/{job_slug}/applications/export",
        { params: { path: { org_slug: org, job_slug: jobSlug } }, parseAs: "text" },
      );
      const code = response.status;
      if (error || typeof data !== "string") throw apiErrorFrom(code, error);
      saveCsv(`applicants-${jobSlug}.csv`, data);
    },
  });

  const setStatus = useMutation({
    mutationFn: async ({
      id,
      status,
      message,
    }: {
      id: string;
      status: EmployerStatus;
      message?: string;
    }) => {
      const { error, response } = await api.PATCH(
        "/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
        {
          params: { path: { org_slug: org, job_slug: jobSlug, application_id: id } },
          body: { status, message: message || undefined },
        },
      );
      // Read before the check, and keep what the server said: "only a hired
      // application can be marked completed" is worth showing.
      const code = response.status;
      if (error) throw apiErrorFrom(code, error);
    },
    // Every mutation that can fail needs an onError: a form that silently does
    // nothing is worse than an error (Sprint 14).
    onSuccess: async (_data, variables) => {
      setDrafts((d) => ({ ...d, [variables.id]: "" }));
      await qc.invalidateQueries({ queryKey: key });
      // A hire can fill the last position and close the vacancy, which moves
      // the dashboard, the workspace's job list and the public counts.
      void qc.invalidateQueries({ queryKey: employerDashboardKey(org) });
      void qc.invalidateQueries({ queryKey: ["org-jobs", org] });
      invalidatePublicCounts(qc);
    },
  });

  // The employer rating the worker. The server fixes the direction by route.
  const rateWorker =
    (applicationId: string) =>
    async (review: { rating: number; comment: string | null }) => {
      const { error, response } = await api.POST(
        "/org/{org_slug}/jobs/{job_slug}/applications/{application_id}/review",
        {
          params: {
            path: { org_slug: org, job_slug: jobSlug, application_id: applicationId },
          },
          body: review,
        },
      );
      const code = response.status;
      if (error) throw apiErrorFrom(code, error);
    };

  if (isPending) return <Skeleton className="mt-8 h-40 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;

  const items = data.items ?? [];
  const isGig = data.job.employment_type === "gig";

  return (
    <div className="mt-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">
          {data.job.title}
        </h1>
        <div className="flex items-center gap-3">
          <Badge>{t("count", { count: data.total })}</Badge>
          {data.total > 0 && (
            <Button
              variant="secondary"
              size="sm"
              disabled={exportCsv.isPending}
              onClick={() => exportCsv.mutate()}
            >
              {t("exportCsv")}
            </Button>
          )}
        </div>
      </div>
      {exportCsv.isError && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-danger-border bg-danger-surface px-3 py-2 text-sm text-danger-text"
        >
          {detailOf(exportCsv.error) ?? t("exportFailed")}
        </p>
      )}
      <ButtonLink href={`/employer/${org}`} variant="ghost" size="sm" className="-ml-3 mt-2">
        ← {t("backToConsole")}
      </ButtonLink>

      {items.length === 0 ? (
        <EmptyState icon={UsersIcon} title={t("empty")} className="mt-8" />
      ) : (
        <ul className="mt-6 space-y-4">
          {items.map((applicant) => {
            const withdrawn = applicant.status === "withdrawn";
            const ended = ENDED.includes(applicant.status);
            // This row's own save, not "some row's": one failed or pending save
            // used to show its error and disable its buttons on every card.
            const mine = setStatus.variables?.id === applicant.application_id;
            return (
              <li key={applicant.application_id}>
                <Card>
                  <CardBody>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-base font-semibold">
                          {applicant.contact?.full_name ?? applicant.candidate.reference}
                        </p>
                        {applicant.candidate.headline && (
                          <p className="text-sm text-muted">{applicant.candidate.headline}</p>
                        )}
                        <p className="mt-0.5 text-xs text-muted">
                          {t("appliedOn", {
                            date: format.dateTime(new Date(applicant.applied_at), {
                              dateStyle: "medium",
                            }),
                          })}
                        </p>
                      </div>
                      <div className="flex max-w-full shrink-0 flex-wrap items-center gap-2">
                        {applicant.status === "applied" && (
                          <StatusChip tone="good" icon={InboxIcon}>
                            {t("newBadge")}
                          </StatusChip>
                        )}
                        {["shortlisted", "rejected", "hired", "completed", "no_show"].includes(
                          applicant.status,
                        ) && (
                          <StatusChip
                            tone={APPLICATION_LOOK[applicant.status].tone}
                            icon={APPLICATION_LOOK[applicant.status].icon}
                          >
                            {t(`status.${applicant.status}`)}
                          </StatusChip>
                        )}
                        <StatusChip tone="neutral" icon={TargetIcon}>
                          {tc("matchScore", { score: applicant.candidate.score })}
                        </StatusChip>
                      </div>
                    </div>

                    <div className="mt-3">
                      <CoverageBar
                        coverage={applicant.candidate.coverage}
                        missingMandatory={applicant.candidate.missing_mandatory}
                        capped={applicant.candidate.capped_by_mandatory}
                      />
                    </div>

                    {withdrawn ? (
                      <p className="mt-4 rounded-lg border border-warning-border bg-warning-surface px-3 py-2 text-sm text-warning-text">
                        {t("withdrawnNote")}
                      </p>
                    ) : (
                      applicant.contact && (
                        <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
                          <dt className="text-muted">{t("contactHeading")}</dt>
                          <dd>
                            {[applicant.contact.phone, applicant.contact.email]
                              .filter(Boolean)
                              .join(" · ")}
                          </dd>
                        </dl>
                      )
                    )}

                    {applicant.message && (
                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                          {t("noteHeading")}
                        </p>
                        <p className="mt-1 text-sm">{applicant.message}</p>
                      </div>
                    )}

                    {ended && (
                      <p className="mt-4 text-sm text-muted">{t("endedNote")}</p>
                    )}

                    {/* `no_show` is deliberately not reviewable: the status
                        already is the evidence, and there was no work to rate. */}
                    {isGig && applicant.status === "completed" &&
                      (applicant.reviewed ? (
                        <p className="mt-3 text-sm text-muted">{tr("givenWorker")}</p>
                      ) : (
                        <ReviewControl
                          prompt={tr("promptWorker")}
                          submit={rateWorker(applicant.application_id)}
                          onSaved={() => qc.invalidateQueries({ queryKey: key })}
                        />
                      ))}

                    {applicant.status_message && (
                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                          {t("youTold")}
                          {applicant.status_message_at &&
                            ` · ${format.dateTime(new Date(applicant.status_message_at), {
                              dateStyle: "medium",
                            })}`}
                        </p>
                        <p className="mt-1 whitespace-pre-wrap text-sm">{applicant.status_message}</p>
                      </div>
                    )}

                    {!withdrawn && !ended && (
                      <div className="mt-4">
                        <label
                          className="block text-sm font-medium"
                          htmlFor={`message-${applicant.application_id}`}
                        >
                          {t("messageLabel")}
                        </label>
                        <textarea
                          id={`message-${applicant.application_id}`}
                          name="status_message"
                          rows={2}
                          maxLength={STATUS_MESSAGE_MAX}
                          value={drafts[applicant.application_id] ?? ""}
                          onChange={(event) =>
                            setDrafts((d) => ({
                              ...d,
                              [applicant.application_id]: event.target.value,
                            }))
                          }
                          className="mt-1 w-full rounded-lg border border-input-border bg-background px-3 py-2 text-sm"
                        />
                        <p className="mt-1 text-xs text-muted">{t("messageHint")}</p>
                      </div>
                    )}

                    {!withdrawn && !ended && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(["shortlisted", "rejected", "hired"] as const).map((status) => (
                          <Button
                            key={status}
                            size="sm"
                            variant={applicant.status === status ? "primary" : "secondary"}
                            disabled={setStatus.isPending && mine}
                            onClick={() =>
                              setStatus.mutate({
                                id: applicant.application_id,
                                status,
                                message: drafts[applicant.application_id]?.trim(),
                              })
                            }
                          >
                            {status === "shortlisted"
                              ? t("shortlist")
                              : status === "rejected"
                                ? t("reject")
                                : t("hire")}
                          </Button>
                        ))}
                        {isGig &&
                          applicant.status === "hired" &&
                          (["completed", "no_show"] as const).map((status) => (
                            <Button
                              key={status}
                              size="sm"
                              variant="secondary"
                              disabled={setStatus.isPending && mine}
                              onClick={() =>
                                setStatus.mutate({
                                id: applicant.application_id,
                                status,
                                message: drafts[applicant.application_id]?.trim(),
                              })
                              }
                            >
                              {status === "completed" ? t("markCompleted") : t("markNoShow")}
                            </Button>
                          ))}
                      </div>
                    )}

                    <ApplicantNotes
                      org={org}
                      jobSlug={jobSlug}
                      applicationId={applicant.application_id}
                      notes={applicant.notes ?? ""}
                      onSaved={() => qc.invalidateQueries({ queryKey: key })}
                    />

                    {setStatus.isError && mine && (
                      <p
                        role="alert"
                        className="mt-3 rounded-lg border border-danger-border bg-danger-surface px-3 py-2 text-sm text-danger-text"
                      >
                        {detailOf(setStatus.error) ?? t("errorGeneric")}
                      </p>
                    )}
                  </CardBody>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
