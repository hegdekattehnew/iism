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
 * The one thing a learner can finally *do* with a recommended course.
 *
 * Until Sprint 24 this page ended in a dead end: the product named the gap,
 * named the course that closes it, and offered nothing to press — while the
 * provider who published it was told nothing at all.
 *
 * **The confirm step is the consent moment, so it says exactly what registering
 * discloses**, names the provider it goes to, and says that withdrawing takes
 * it back. The same shape as `ApplyPanel`, minus the save half: there is no
 * saved-courses table, and a button that stores nothing would be a lie.
 *
 * An organisation-only account is offered nothing. It cannot register —
 * `get_current_candidate` refuses — and an affordance that always fails is
 * worse than no affordance.
 */

const ALERT =
  "mt-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 " +
  "dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300";

function useMyInterests(enabled: boolean) {
  return useQuery({
    queryKey: ["me", "course-interests"],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET("/me/course-interests");
      if (error || !data) throw new Error("interests failed");
      return data;
    },
  });
}

export function InterestPanel({
  courseSlug,
  organisation,
}: {
  courseSlug: string;
  organisation: string;
}) {
  const t = useTranslations("courseInterest");
  const signedIn = useIsSignedIn();
  const { isJobSeeker, isPending: membershipsPending } = useMemberships();
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const interests = useMyInterests(signedIn);
  const mine = interests.data?.find((i) => i.course.slug === courseSlug);
  const live = mine && mine.status !== "withdrawn";

  const register = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, error: err, response } = await api.POST("/me/course-interests", {
        body: { course_slug: courseSlug, message: message.trim() || null },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: async () => {
      setConfirming(false);
      setMessage("");
      await qc.invalidateQueries({ queryKey: ["me", "course-interests"] });
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
        "/me/course-interests/{interest_id}/withdraw",
        { params: { path: { interest_id: mine.id } } },
      );
      if (err) throw new Error(String(response.status));
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me", "course-interests"] });
    },
    onError: () => setError(t("errorGeneric")),
  });

  if (!signedIn) {
    return (
      <ButtonLink href="/signin" size="lg">
        {t("signInToRegister")}
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
              {t("registeredLabel")}
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
            {t("register")}
          </Button>
        )}
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
            <Button onClick={() => register.mutate()} disabled={register.isPending}>
              {register.isPending ? t("registering") : t("confirmCta")}
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
