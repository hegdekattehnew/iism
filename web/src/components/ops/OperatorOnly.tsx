"use client";

import { useTranslations } from "next-intl";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { ButtonLink } from "@/components/ui";
import { useMemberships } from "@/lib/org";

/**
 * The back office's front door.
 *
 * **Not-found, not "no access"** -- the same answer `require_operator` gives
 * (ADR-042). A 403-shaped page would tell somebody who found `/admin` that
 * they had found the back office and that one flag on their row was all that
 * stood in the way. There is nothing to acknowledge here: a non-operator has
 * established no standing at all, which is exactly when 404 is the honest
 * refusal.
 *
 * **Signed out is a different answer and must stay different.** It is not a
 * permission problem -- it is "you are not anybody yet" -- and rendering
 * not-found for it would send somebody who simply needs to sign in away for
 * good. Same distinction `SessionExpired` exists for, one layer up.
 *
 * `is_staff` rides on `/auth/me`, so this costs no extra request: it reads the
 * query every signed-in screen already makes.
 */
export function OperatorOnly({ children }: { children: ReactNode }) {
  const t = useTranslations("ops");
  const me = useMemberships();

  // Nothing is known yet. Rendering not-found here would 404 every operator
  // for the length of one request, which is the bug a test pins.
  if (me.isPending) return null;

  if (!me.data) {
    return (
      <div className="mx-auto w-full max-w-2xl px-5 py-16 text-center">
        <h1 className="text-2xl font-bold tracking-tight">{t("signedOutTitle")}</h1>
        <p className="mt-2 text-muted">{t("signedOutBody")}</p>
        <div className="mt-6">
          <ButtonLink href="/signin">{t("signIn")}</ButtonLink>
        </div>
      </div>
    );
  }

  if (!me.data.is_staff) notFound();

  return <>{children}</>;
}
