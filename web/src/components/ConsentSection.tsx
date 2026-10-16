"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Alert, Button, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useConfirmConsent, useConsentState, useWithdrawConsent } from "@/lib/consent";
import { detailOf } from "@/lib/http";

/**
 * What the person agreed to, and the two things they can do about it without deleting anything
 * (Sprint 72, ADR-082): **withdraw consent** (a pause, with what it takes back shown first) and,
 * once withdrawn or when the notice has changed, **confirm the notice again**.
 *
 * Withdrawing is two steps for the reason deleting is: the second shows who currently holds the
 * person's contact details, fetched from the API, before the button that ends it. It is the
 * reverse of `AccountPanel`'s deletion, and it says so: this is a pause, not an erasure.
 */
export function ConsentSection() {
  const t = useTranslations("account");
  const format = useFormatter();
  const state = useConsentState();
  const [confirming, setConfirming] = useState(false);
  const withdraw = useWithdrawConsent();
  const confirm = useConfirmConsent();

  const given = state.data;
  const date = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium" });

  return (
    <section
      aria-labelledby="consent-heading"
      className="rounded-xl border border-border-token bg-surface p-5"
    >
      <h2 id="consent-heading" className="text-base font-semibold">
        {t("consentTitle")}
      </h2>
      {/* A line of text arrives late and is a different length: reserve it. */}
      {state.isPending ? (
        <Skeleton className="mt-1 h-5 w-3/4" />
      ) : given?.withdrawn && given.consent_withdrawn_at ? (
        <p className="mt-1 text-sm text-muted">
          {t("consentStatusPaused", { date: date(given.consent_withdrawn_at) })}
        </p>
      ) : given?.consent_version && given.consented_at ? (
        <p className="mt-1 text-sm text-muted">
          {t("consentGiven", { version: given.consent_version, date: date(given.consented_at) })}
        </p>
      ) : (
        <p className="mt-1 text-sm text-muted">{t("consentMissing")}</p>
      )}
      <p className="mt-2 text-sm">
        <Link href="/privacy" className="text-brand underline underline-offset-4 hover:text-brand-strong">
          {t("readNotice")}
        </Link>
      </p>

      {given?.withdrawn ? (
        <div className="mt-4 rounded-lg border border-border-token p-4">
          <h3 className="text-sm font-semibold">{t("restoreTitle")}</h3>
          <p className="mt-1 text-sm text-muted">{t("restoreBody")}</p>
          <Button className="mt-3" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
            {confirm.isPending ? t("bannerConfirming") : t("restoreButton")}
          </Button>
          {confirm.isError && (
            <Alert className="mt-3">{detailOf(confirm.error) ?? t("bannerError")}</Alert>
          )}
        </div>
      ) : (
        <div className="mt-4 border-t border-border-token pt-4">
          <h3 className="text-sm font-semibold">{t("withdrawTitle")}</h3>
          <p className="mt-1 text-sm text-muted">{t("withdrawBody")}</p>
          {!confirming ? (
            <Button variant="secondary" className="mt-3" onClick={() => setConfirming(true)}>
              {t("withdrawButton")}
            </Button>
          ) : (
            <div className="mt-3 rounded-lg border border-border-token p-4">
              <h4 className="text-sm font-semibold">{t("withdrawPreviewTitle")}</h4>
              {state.isError ? (
                <Alert className="mt-3">{t("withdrawError")}</Alert>
              ) : (
                <>
                  <p className="mt-2 text-sm">
                    {given && given.live_applications + given.live_interests > 0
                      ? t("withdrawHolders", {
                          applications: given.live_applications,
                          interests: given.live_interests,
                        })
                      : t("withdrawNoHolders")}
                  </p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    <li>{t("withdrawEffectPool")}</li>
                    <li>{t("withdrawEffectApply")}</li>
                    <li>{t("withdrawEffectTrack")}</li>
                    <li>{t("withdrawEffectStill")}</li>
                  </ul>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Button
                      variant="danger"
                      disabled={withdraw.isPending}
                      onClick={() => withdraw.mutate()}
                    >
                      {withdraw.isPending ? t("withdrawing") : t("withdrawConfirm")}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setConfirming(false);
                        withdraw.reset();
                      }}
                    >
                      {t("cancel")}
                    </Button>
                  </div>
                  {withdraw.isError && (
                    <Alert className="mt-3">{detailOf(withdraw.error) ?? t("withdrawError")}</Alert>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
