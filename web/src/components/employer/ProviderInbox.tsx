"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { Badge, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { providerDashboardKey } from "@/lib/counts";
import { ApiError, detailOf, readDetail } from "@/lib/http";

// What a provider may set, from the generated schema. The mutation used to
// hardcode "contacted", so a provider had no way to record an enrolment and the
// dashboard's enrolled tile could only ever be fed by seed data.
type ProviderStatus = components["schemas"]["ProviderStatusIn"]["status"];

/**
 * Who wants this course, and how to reach them.
 *
 * **Contact details appear here and nowhere else in the provider surface.**
 * They are present because the learner registered interest, and absent the
 * moment they withdraw — the row stays so the provider's own history is not
 * rewritten, and `contact` comes back null.
 *
 * **There is no score and no coverage bar, unlike the employer's inbox.** A
 * vacancy publishes the standards it requires, so an applicant can be ranked
 * against them; a course publishes what it *teaches*, so there is nothing to
 * rank a learner against — and inventing something would be the second scorer
 * ADR-037 forbids.
 */
export function ProviderInbox({ org, courseSlug }: { org: string; courseSlug: string }) {
  const t = useTranslations("providerInbox");
  const format = useFormatter();
  const qc = useQueryClient();

  const key = ["org", org, "interests", courseSlug];
  const { data, isPending, isError } = useQuery({
    queryKey: key,
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/org/{org_slug}/courses/{course_slug}/interests",
        { params: { path: { org_slug: org, course_slug: courseSlug } } },
      );
      if (error || !data) throw new Error("inbox failed");
      return data;
    },
  });

  const setStatus = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: ProviderStatus }) => {
      const { error, response } = await api.PATCH(
        "/org/{org_slug}/courses/{course_slug}/interests/{interest_id}",
        {
          params: { path: { org_slug: org, course_slug: courseSlug, interest_id: id } },
          body: { status },
        },
      );
      const code = response.status;
      if (error) throw new ApiError(code, readDetail(error));
    },
    // Every mutation that can fail needs an onError: a button that silently
    // does nothing is worse than an error (Sprint 14).
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: key });
      await qc.invalidateQueries({ queryKey: ["org", org, "interests"] });
      void qc.invalidateQueries({ queryKey: providerDashboardKey(org) });
    },
  });

  if (isPending) return <Skeleton className="mt-8 h-40 w-full" />;
  if (isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;

  const items = data.items ?? [];

  return (
    <div className="mt-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight">{data.course.title}</h1>
        <Badge>{t("count", { count: data.total })}</Badge>
      </div>
      <ButtonLink href={`/employer/${org}`} variant="ghost" size="sm" className="-ml-3 mt-2">
        ← {t("backToConsole")}
      </ButtonLink>

      {items.length === 0 ? (
        <p className="mt-8 text-sm text-muted">{t("empty")}</p>
      ) : (
        <ul className="mt-6 space-y-4">
          {items.map((learner) => {
            const withdrawn = learner.status === "withdrawn";
            // This row's own save, not "some row's".
            const mine = setStatus.variables?.id === learner.interest_id;
            return (
              <li key={learner.interest_id}>
                <Card>
                  <CardBody>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-base font-semibold">
                          {learner.contact?.full_name ?? t("withdrawnTitle")}
                        </p>
                        {(learner.location_district || learner.location_state) && (
                          <p className="text-sm text-muted">
                            {[learner.location_district, learner.location_state]
                              .filter(Boolean)
                              .join(", ")}
                          </p>
                        )}
                        <p className="mt-0.5 text-xs text-muted">
                          {t("registeredOn", {
                            date: format.dateTime(new Date(learner.registered_at), {
                              dateStyle: "medium",
                            }),
                          })}
                        </p>
                      </div>
                      {learner.status === "registered" && (
                        <Badge tone="good">{t("newBadge")}</Badge>
                      )}
                      {learner.status === "contacted" && <Badge>{t("contactedBadge")}</Badge>}
                      {learner.status === "enrolled" && <Badge tone="good">{t("enrolledBadge")}</Badge>}
                    </div>

                    {withdrawn ? (
                      <p className="mt-4 rounded-lg border border-warning-border bg-warning-surface px-3 py-2 text-sm text-warning-text">
                        {t("withdrawnNote")}
                      </p>
                    ) : (
                      learner.contact && (
                        <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
                          <dt className="text-muted">{t("contactHeading")}</dt>
                          <dd>
                            {[learner.contact.phone, learner.contact.email]
                              .filter(Boolean)
                              .join(" · ")}
                          </dd>
                        </dl>
                      )
                    )}

                    {learner.message && (
                      <div className="mt-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                          {t("noteHeading")}
                        </p>
                        <p className="mt-1 text-sm">{learner.message}</p>
                      </div>
                    )}

                    {/* Forward only: "contacted" is offered to somebody who has not
                        been, "enrolled" to anybody not yet enrolled. An enrolled
                        learner used to be offered "contacted" and could be moved
                        back without a word. */}
                    {!withdrawn && learner.status !== "enrolled" && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {learner.status === "registered" && (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={setStatus.isPending && mine}
                            onClick={() =>
                              setStatus.mutate({ id: learner.interest_id, status: "contacted" })
                            }
                          >
                            {setStatus.isPending && mine ? t("saving") : t("markContacted")}
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={setStatus.isPending && mine}
                          onClick={() =>
                            setStatus.mutate({ id: learner.interest_id, status: "enrolled" })
                          }
                        >
                          {t("markEnrolled")}
                        </Button>
                      </div>
                    )}
                    {setStatus.isError && mine && (
                      <p role="alert" className="mt-3 text-sm text-danger-text">
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
