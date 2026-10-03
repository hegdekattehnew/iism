"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { CoverageBar } from "@/components/CoverageBar";
import { ReviewControl } from "@/components/ReviewControl";
import { Badge, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { employerDashboardKey, invalidatePublicCounts } from "@/lib/counts";
import { ApiError, detailOf, readDetail } from "@/lib/http";

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

  const setStatus = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: EmployerStatus }) => {
      const { error, response } = await api.PATCH(
        "/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
        {
          params: { path: { org_slug: org, job_slug: jobSlug, application_id: id } },
          body: { status },
        },
      );
      // Read before the check, and keep what the server said: "only a hired
      // application can be marked completed" is worth showing.
      const code = response.status;
      if (error) throw new ApiError(code, readDetail(error));
    },
    // Every mutation that can fail needs an onError: a form that silently does
    // nothing is worse than an error (Sprint 14).
    onSuccess: async () => {
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
      if (error) throw new ApiError(code, readDetail(error));
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
        <Badge>{t("count", { count: data.total })}</Badge>
      </div>
      <ButtonLink href={`/employer/${org}`} variant="ghost" size="sm" className="-ml-3 mt-2">
        ← {t("backToConsole")}
      </ButtonLink>

      {items.length === 0 ? (
        <p className="mt-8 text-sm text-muted">{t("empty")}</p>
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
                      <div className="flex shrink-0 items-center gap-2">
                        {applicant.status === "applied" && <Badge tone="good">{t("newBadge")}</Badge>}
                        {["shortlisted", "rejected", "hired", "completed", "no_show"].includes(
                          applicant.status,
                        ) && <Badge>{t(`status.${applicant.status}`)}</Badge>}
                        <Badge>{tc("matchScore", { score: applicant.candidate.score })}</Badge>
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

                    {!withdrawn && !ended && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {(["shortlisted", "rejected", "hired"] as const).map((status) => (
                          <Button
                            key={status}
                            size="sm"
                            variant={applicant.status === status ? "primary" : "secondary"}
                            disabled={setStatus.isPending && mine}
                            onClick={() =>
                              setStatus.mutate({ id: applicant.application_id, status })
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
                                setStatus.mutate({ id: applicant.application_id, status })
                              }
                            >
                              {status === "completed" ? t("markCompleted") : t("markNoShow")}
                            </Button>
                          ))}
                      </div>
                    )}

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
