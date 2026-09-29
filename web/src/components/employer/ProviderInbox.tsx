"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { Badge, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";

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
    mutationFn: async (id: string) => {
      const { error, response } = await api.PATCH(
        "/org/{org_slug}/courses/{course_slug}/interests/{interest_id}",
        {
          params: { path: { org_slug: org, course_slug: courseSlug, interest_id: id } },
          body: { status: "contacted" },
        },
      );
      if (error) throw new Error(String(response.status));
    },
    // Every mutation that can fail needs an onError: a button that silently
    // does nothing is worse than an error (Sprint 14).
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: key });
      await qc.invalidateQueries({ queryKey: ["org", org, "interests"] });
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

                    {!withdrawn && learner.status !== "contacted" && (
                      <div className="mt-4">
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={setStatus.isPending}
                          onClick={() => setStatus.mutate(learner.interest_id)}
                        >
                          {setStatus.isPending ? t("saving") : t("markContacted")}
                        </Button>
                      </div>
                    )}
                    {setStatus.isError && (
                      <p role="alert" className="mt-3 text-sm text-danger-text">
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
