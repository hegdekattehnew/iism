"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { ButtonLink, buttonVariants } from "@/components/ui";
import { cn } from "@/lib/cn";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { clearTokens, getRefreshToken, useIsSignedIn } from "@/lib/auth";

/** Header auth controls. Rendered client-side, because whether someone is
 *  signed in is only knowable in the browser. */
export function AuthNav({ stacked = false }: { stacked?: boolean }) {
  const t = useTranslations("auth");
  const tn = useTranslations("nav");
  const router = useRouter();
  const qc = useQueryClient();
  const signedIn = useIsSignedIn();

  const signOut = async () => {
    const refresh_token = getRefreshToken();
    // Revoke server-side first; clearing locally alone would leave a valid
    // refresh token in play for 30 days.
    if (refresh_token)
      await api.POST("/auth/logout", { body: { refresh_token } });
    clearTokens();
    // The QueryClient is created once per browser session, so without this the
    // previous person's profile, matches, memberships and vacancies stay in
    // memory and render to whoever signs in next until fresh queries resolve.
    // Same concern that put /me/, /profile and /matches on the service worker's
    // DENY list -- and the target device is a shared phone.
    qc.clear();
    router.push("/");
  };

  const size = stacked ? "lg" : "sm";

  if (signedIn) {
    return (
      <>
        <ButtonLink href="/matches" size={size}>
          {t("myMatches")}
        </ButtonLink>
        <ButtonLink href="/profile" variant="secondary" size={size}>
          {t("myProfile")}
        </ButtonLink>
        <button
          type="button"
          onClick={() => void signOut()}
          className={cn(
            buttonVariants({ variant: "ghost", size }),
            "text-foreground",
          )}
        >
          {t("signOut")}
        </button>
      </>
    );
  }

  return (
    <>
      <Link
        href="/signin"
        className={cn(
          buttonVariants({ variant: "ghost", size }),
          "text-foreground",
        )}
      >
        {tn("signIn")}
      </Link>
      {/* `/signup`, not `/signup/seeker`. This header renders on every route,
          so hardcoding the job-seeker path offered an employer reading `/jobs`
          the one signup they did not want and no sign of the other two. */}
      <ButtonLink href="/signup" size={size}>
        {tn("getStarted")}
      </ButtonLink>
    </>
  );
}
