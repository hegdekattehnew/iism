"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Area } from "@/components/profile/fields";
import { Button, ButtonLink } from "@/components/ui";
import { api } from "@/lib/api";
import { useIsSignedIn } from "@/lib/auth";
import { useMemberships } from "@/lib/org";

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

const ALERT =
  "mt-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 " +
  "dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300";

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
}: {
  jobSlug: string;
  organisation: string;
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
    },
    onError: () => setError(t("errorGeneric")),
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

  if (!signedIn) {
    return (
      <ButtonLink href="/signin" size="lg">
        {t("signInToApply")}
      </ButtonLink>
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
            <span className="inline-flex items-center rounded-lg bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300">
              {t("appliedLabel")}
            </span>
            <Button
              variant="ghost"
              onClick={() => withdraw.mutate()}
              disabled={withdraw.isPending}
            >
              {withdraw.isPending ? t("withdrawing") : t("withdraw")}
            </Button>
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
        <div className="mt-4 rounded-xl border border-border-token bg-surface p-4">
          <h2 className="text-base font-semibold">{t("confirmHeading")}</h2>
          {/* The disclosure, named in full, before the act that makes it. */}
          <p className="mt-2 text-sm">{t("confirmShare", { organisation })}</p>
          <p className="mt-1 text-sm text-muted">{t("confirmWithdrawNote")}</p>

          <label className="mt-4 block text-sm">
            <span className="font-medium">{t("messageLabel")}</span>
            <Area
              value={message}
              maxLength={1000}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={t("messagePlaceholder")}
            />
          </label>

          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={() => apply.mutate()} disabled={apply.isPending}>
              {apply.isPending ? t("applying") : t("confirmCta")}
            </Button>
            <Button
              variant="ghost"
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

      {error && (
        <p role="alert" className={ALERT}>
          {error}
        </p>
      )}
    </div>
  );
}
