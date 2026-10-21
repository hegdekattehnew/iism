"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert, Button, ButtonLink } from "@/components/ui";
import { Field, Textarea } from "@/components/ui/field";
import { IconTile } from "@/components/ui/icon-tile";
import { ShieldCheckIcon } from "@/components/ui/icons";
import { api } from "@/lib/api";
import { useIsSignedIn } from "@/lib/auth";
import { invalidatePublicCounts } from "@/lib/counts";
import type { components } from "@/lib/api-schema";
import { useMemberships } from "@/lib/org";

type Status = components["schemas"]["ApplicationOut"]["status"];

/** What a candidate may still take back. The server's `WITHDRAWABLE_STATUSES`: once
 *  an employer has decided, withdrawing would rewrite their record rather than end
 *  the candidate's own interest. Typed against the schema so a renamed status is a
 *  compile error, not a button that silently never appears. */
const WITHDRAWABLE: readonly Status[] = ["applied", "shortlisted"];

/**
 * Apply, and save for later — the two things a candidate can finally *do*.
 *
 * **The confirm step is the consent moment, so it says exactly what applying
 * discloses**, names the employer it goes to, and says that withdrawing takes
 * it back. Nothing is pre-ticked and the button that discloses is the one
 * labelled to disclose; the API records the same act as
 * `contact_shared_at`.
 *
 * An organisation-only account is offered neither control. It cannot apply —
 * `get_current_candidate` refuses — and an affordance that always fails is
 * worse than no affordance.
 */


/** The caller's applications, shared by every button on the page. */
function useMyApplications(enabled: boolean) {
  return useQuery({
    queryKey: ["me", "applications"],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET("/me/applications");
      if (error || !data) throw new Error("applications failed");
      return data;
    },
  });
}

function useMySavedJobs(enabled: boolean) {
  return useQuery({
    queryKey: ["me", "saved-jobs"],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET("/me/saved-jobs");
      if (error || !data) throw new Error("saved failed");
      return data;
    },
  });
}

export function ApplyPanel({
  jobSlug,
  organisation,
  isOpen = true,
}: {
  jobSlug: string;
  organisation: string;
  /** Whether the vacancy still takes applications (Sprint 27). The page is
   *  still here when it does not -- people have it bookmarked and it is in
   *  their application list -- so this says so rather than 404ing. */
  isOpen?: boolean;
}) {
  const t = useTranslations("applications");
  const signedIn = useIsSignedIn();
  const { isJobSeeker, isPending: membershipsPending } = useMemberships();
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const applications = useMyApplications(signedIn);
  const saved = useMySavedJobs(signedIn);

  const mine = applications.data?.find((a) => a.job.slug === jobSlug);
  const isSaved = saved.data?.some((s) => s.job.slug === jobSlug) ?? false;
  const live = mine && mine.status !== "withdrawn";
  const canWithdraw = mine ? WITHDRAWABLE.includes(mine.status) : false;

  const apply = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, error: err, response } = await api.POST("/me/applications", {
        body: { job_slug: jobSlug, message: message.trim() || null },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: async () => {
      setConfirming(false);
      setMessage("");
      await qc.invalidateQueries({ queryKey: ["me", "applications"] });
      // "Applications made" is a public figure.
      invalidatePublicCounts(qc);
    },
    onError: (e: Error) => {
      const status = Number(e.message);
      setError(
        status === 409
          ? t("errorDuplicate")
          : status === 429
            ? t("errorCap")
            : status === 403
              ? t("errorSeeker")
              : t("errorGeneric"),
      );
    },
  });

  const withdraw = useMutation({
    mutationFn: async () => {
      setError(null);
      if (!mine) return;
      const { error: err, response } = await api.POST(
        "/me/applications/{application_id}/withdraw",
        { params: { path: { application_id: mine.id } } },
      );
      if (err) throw new Error(String(response.status));
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me", "applications"] });
      invalidatePublicCounts(qc);
    },
    onError: (e: Error) =>
      setError(Number(e.message) === 409 ? t("errorWithdrawDecided") : t("errorGeneric")),
  });

  const toggleSave = useMutation({
    mutationFn: async () => {
      setError(null);
      if (isSaved) {
        await api.DELETE("/me/saved-jobs/{job_slug}", {
          params: { path: { job_slug: jobSlug } },
        });
        return;
      }
      const { error: err, response } = await api.POST("/me/saved-jobs", {
        body: { job_slug: jobSlug },
      });
      if (err) throw new Error(String(response.status));
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me", "saved-jobs"] });
    },
    onError: () => setError(t("errorGeneric")),
  });

  // **Before the sign-in prompt.** A closed vacancy takes nobody's
  // application, so asking a signed-out visitor to sign in first would walk
  // them through an account to reach a 409.
  if (!isOpen && !live) {
    return <Alert tone="warning">{t("vacancyClosed")}</Alert>;
  }
  if (!signedIn) {
    return (
      <div>
        <ButtonLink href="/signin" size="lg">
          {t("signInToApply")}
        </ButtonLink>
        {/* What signing in costs, said before it is pressed (Sprint 92). */}
        <p className="mt-1.5 text-xs text-muted">{t("signInToApplyHint")}</p>
      </div>
    );
  }
  // Nothing at all for an organisation-only account, and nothing while we do
  // not yet know which this is: a button that appears and then vanishes is
  // worse than one that arrives a moment late.
  if (membershipsPending || !isJobSeeker) return null;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        {live ? (
          <>
            <span
              className={`inline-flex items-center rounded-lg px-3 py-2 text-sm font-semibold ${
                mine.status === "rejected"
                  ? "bg-warning-surface text-warning-text"
                  : "bg-success-surface text-success-text"
              }`}
            >
              {/* "Applied" for a live application, and the employer's own word once
                  they have decided: a rejected candidate told "Applied" is misled. */}
              {mine.status === "applied" || mine.status === "shortlisted"
                ? t("appliedLabel")
                : t(`status.${mine.status}`)}
            </span>
            {canWithdraw && (
              <Button
                variant="ghost"
                onClick={() => withdraw.mutate()}
                disabled={withdraw.isPending}
              >
                {withdraw.isPending ? t("withdrawing") : t("withdraw")}
              </Button>
            )}
          </>
        ) : (
          <Button size="lg" onClick={() => setConfirming(true)}>
            {t("apply")}
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={() => toggleSave.mutate()}
          disabled={toggleSave.isPending}
        >
          {isSaved ? t("savedLabel") : t("save")}
        </Button>
      </div>

      {confirming && !live && (
        <div
          role="group"
          aria-labelledby="apply-confirm-heading"
          className="mt-4 rounded-xl border border-border-token bg-surface p-4 shadow-card"
        >
          {/* The disclosure, named in full, before the act that makes it. The words are the ones this
              step has always said (Sprint 86 changed the layout, not what it tells the person). */}
          <div className="flex items-start gap-3">
            <IconTile tone="info">
              <ShieldCheckIcon />
            </IconTile>
            <div className="min-w-0 flex-1">
              <h2 id="apply-confirm-heading" className="text-base font-semibold">
                {t("confirmHeading")}
              </h2>
              <p className="mt-1 text-sm">{t("confirmShare", { organisation })}</p>
              <p className="mt-1 text-sm text-muted">{t("confirmWithdrawNote")}</p>
            </div>
          </div>

          {/* What the person typed stays when the request fails or the step is closed and reopened:
              `message` is cleared only by a success. */}
          <Field label={t("messageLabel")} className="mt-4">
            <Textarea
              name="message"
              value={message}
              maxLength={1000}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={t("messagePlaceholder")}
            />
          </Field>

          {/* Beside the buttons that caused it: the bar this sits in scrolls on a short phone, and an
              error under the box was out of sight. */}
          {error && (
            <Alert className="mt-3" role="alert">
              {error}
            </Alert>
          )}

          <div className="mt-4 flex flex-col gap-2 sm:flex-row-reverse sm:justify-start">
            <Button className="w-full sm:w-auto" onClick={() => apply.mutate()} disabled={apply.isPending}>
              {apply.isPending ? t("applying") : t("confirmCta")}
            </Button>
            <Button
              variant="ghost"
              className="w-full sm:w-auto"
              onClick={() => {
                setConfirming(false);
                setError(null);
              }}
            >
              {t("cancel")}
            </Button>
          </div>
        </div>
      )}

      {error && !(confirming && !live) && (
        <Alert className="mt-3">
          {error}
        </Alert>
      )}
    </div>
  );
}
