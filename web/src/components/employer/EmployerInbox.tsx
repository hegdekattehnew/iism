"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { CoverageBar } from "@/components/CoverageBar";
import { Badge, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";

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
    mutationFn: async ({ id, status }: { id: string; status: "shortlisted" | "rejected" | "hired" }) => {
      const { error, response } = await api.PATCH(
        "/org/{org_slug}/jobs/{job_slug}/applications/{application_id}",
        {
          params: { path: { org_slug: org, job_slug: jobSlug, application_id: id } },
          body: { status },
        },
      );
      if (error) throw new Error(String(response.status));
    },
    // Every mutation that can fail needs an onError: a form that silently does
    // nothing is worse than an error (Sprint 14).
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: key });
      await qc.invalidateQueries({ queryKey: ["org", org, "overview"] });
    },
  });

  if (isPending) return <Skeleton className="mt-8 h-40 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;

  const items = data.items ?? [];

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
                      <p className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
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

                    {!withdrawn && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {(["shortlisted", "rejected", "hired"] as const).map((status) => (
                          <Button
                            key={status}
                            size="sm"
                            variant={applicant.status === status ? "primary" : "secondary"}
                            disabled={setStatus.isPending}
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
                      </div>
                    )}

                    {setStatus.isError && (
                      <p
                        role="alert"
                        className="mt-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
                      >
                        {t("errorGeneric")}
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
