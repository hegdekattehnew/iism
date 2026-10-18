"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Alert, Button } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useConfirmConsent } from "@/lib/consent";
import { detailOf } from "@/lib/http";
import { useMemberships } from "@/lib/org";

/**
 * Asks a signed-in person to read and confirm the privacy notice when it is not the one they agreed
 * to, or to switch their account back on after they withdrew consent (Sprint 72, ADR-082).
 *
 * **It never blocks anything.** A stale notice shows this and everything keeps working while the
 * person decides; only an explicit withdrawal switches things off. It reads `/auth/me`, which every
 * signed-in screen already asks for, so it makes no request of its own.
 *
 * **It is fixed to the bottom of the window, not part of the page**, and that is the whole layout
 * decision. It arrives when `/auth/me` does, which is before the page's own data, so any place in
 * the flow made it jump: above the content it pushed everything down, and below it the dashboard
 * landing above it pushed *it* down (`checkPage` measured 0.108 on a phone-sized run, over the 0.1
 * budget, ADR-065). A fixed element moves nothing. "Not now" hides it for this browser session only;
 * it asks again next time, because the notice has still not been confirmed.
 *
 * It is imported by the account, profile and matches pages and not by the header, whose first-load
 * headroom is a few kilobytes.
 */
const DISMISSED = "iism.consent.dismissed";

function wasDismissed(kind: string): boolean {
  try {
    return sessionStorage.getItem(`${DISMISSED}.${kind}`) === "1";
  } catch {
    return false; // private window or blocked storage: show it, never throw
  }
}

export function ConsentBanner() {
  const t = useTranslations("account");
  const { data: me } = useMemberships();
  const confirm = useConfirmConsent();
  // Read once, on the client: the server render and a signed-out visitor both return null below,
  // so the initial value can never disagree with what was rendered.
  const [hidden, setHidden] = useState<Record<string, boolean>>(() => ({
    paused: wasDismissed("paused"),
    stale: wasDismissed("stale"),
  }));

  if (!me) return null;
  const paused = me.consent_withdrawn;
  // An account created before consent was recorded has no version at all: that is the Account
  // page's own sentence, not a banner on every page.
  if (!paused && (me.consent_current || !me.consent_version)) return null;
  const kind = paused ? "paused" : "stale";
  if (hidden[kind]) return null;

  const notNow = () => {
    try {
      sessionStorage.setItem(`${DISMISSED}.${kind}`, "1");
    } catch {
      /* the banner simply comes back next time */
    }
    setHidden((h) => ({ ...h, [kind]: true }));
  };

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-[var(--tabbar)] z-40 px-4 pb-4">
      <Alert
        tone={paused ? "warning" : "info"}
        role="status"
        className="pointer-events-auto mx-auto max-w-3xl space-y-3 shadow-lg"
      >
        <div>
          <p className="font-semibold">{paused ? t("bannerPausedTitle") : t("bannerStaleTitle")}</p>
          <p className="mt-1">{paused ? t("bannerPausedBody") : t("bannerStaleBody")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/privacy" className="underline underline-offset-4">
            {t("bannerRead")}
          </Link>
          <Button size="sm" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
            {confirm.isPending
              ? t("bannerConfirming")
              : paused
                ? t("bannerRestore")
                : t("bannerConfirm")}
          </Button>
          <Button size="sm" variant="ghost" onClick={notNow}>
            {t("bannerNotNow")}
          </Button>
        </div>
        {confirm.isError && <p role="alert">{detailOf(confirm.error) ?? t("bannerError")}</p>}
      </Alert>
    </div>
  );
}
