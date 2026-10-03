"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { SkillChip } from "@/components/GapPanel";
import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Button, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { ApiError, detailOf, isSignedOut, readDetail } from "@/lib/http";

/**
 * Hire and train: for a candidate one standard short, see what teaches it and
 * offer to sponsor it (ADR-048).
 *
 * **What this deliberately does not say.** The candidate is told only if they
 * have not switched off unsolicited messages and are under today's cap, and an
 * opt-out is a fact about them, not about this employer. So the panel never
 * claims the candidate was notified: it says the offer was recorded, and that
 * they appear in the applicants if they choose to apply -- which is the only
 * moment this employer learns who they are (ADR-037).
 */
export function SponsorPanel({
  orgSlug,
  jobSlug,
  reference,
}: {
  orgSlug: string;
  jobSlug: string;
  reference: string;
}) {
  const t = useTranslations("sponsor");
  const tm = useTranslations("matchesPage");
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const key = ["org", orgSlug, "training", jobSlug, reference];
  const params = { path: { org_slug: orgSlug, job_slug: jobSlug, reference } };

  const training = useQuery({
    queryKey: key,
    enabled: open,
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/org/{org_slug}/candidates/{job_slug}/{reference}/training",
        { params },
      );
      const status = response.status;
      if (error || !data) throw new ApiError(status, readDetail(error));
      return data;
    },
  });

  const offer = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.POST(
        "/org/{org_slug}/candidates/{job_slug}/{reference}/sponsor",
        { params },
      );
      const status = response.status;
      if (error) throw new ApiError(status, readDetail(error));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });

  const data = training.data;
  const courses = data?.courses ?? [];

  return (
    <div className="mt-3 border-t border-border-token pt-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`sponsor-${reference}`}
        onClick={() => setOpen((v) => !v)}
        className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        {open ? t("hide") : t("open")}
      </button>

      {open && (
        <div id={`sponsor-${reference}`} className="mt-3 space-y-3">
          {training.isPending && <Skeleton className="h-20 w-full rounded-lg" />}
          {isSignedOut(training.error) && <SessionExpired variant="inline" />}
          {training.isError && !isSignedOut(training.error) && (
            <p className="text-sm text-muted">{detailOf(training.error) ?? t("loadError")}</p>
          )}

          {data && (
            <>
              <p className="text-sm text-muted">{t("intro")}</p>
              <SkillChip skill={data.standard} held={false} />

              {courses.length === 0 ? (
                <p className="text-sm text-muted">{t("noCourses")}</p>
              ) : (
                <ul className="space-y-2">
                  {courses.map((c) => (
                    <li key={c.slug} className="rounded-lg border border-border-token p-3">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <Link
                          href={`/courses/${c.slug}`}
                          className="text-sm font-semibold underline-offset-4 hover:underline"
                        >
                          {c.title}
                        </Link>
                        {c.duration_hours != null && (
                          <span className="text-xs text-muted">
                            {tm("hours", { hours: c.duration_hours })}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {data.offered ? (
                <p className="text-sm font-medium">
                  {offer.isSuccess ? t("recorded") : t("alreadyOffered")}
                </p>
              ) : (
                courses.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs text-muted">{t("consent")}</p>
                    <Button size="sm" disabled={offer.isPending} onClick={() => offer.mutate()}>
                      {offer.isPending ? t("sending") : t("offer")}
                    </Button>
                  </div>
                )
              )}

              {offer.isError && (
                <Alert role="alert">
                  {isSignedOut(offer.error) ? (
                    <SessionExpired variant="inline" />
                  ) : (
                    (detailOf(offer.error) ?? t("failed"))
                  )}
                </Alert>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
