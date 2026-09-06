"use client";

import { useTranslations } from "next-intl";

import { ButtonLink, buttonClass } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { clearTokens, getRefreshToken, useIsSignedIn } from "@/lib/auth";

/** Header auth controls. Rendered client-side, because whether someone is
 *  signed in is only knowable in the browser. */
export function AuthNav({ stacked = false }: { stacked?: boolean }) {
  const t = useTranslations("auth");
  const tn = useTranslations("nav");
  const router = useRouter();
  const signedIn = useIsSignedIn();

  const signOut = async () => {
    const refresh_token = getRefreshToken();
    // Revoke server-side first; clearing locally alone would leave a valid
    // refresh token in play for 30 days.
    if (refresh_token) await api.POST("/auth/logout", { body: { refresh_token } });
    clearTokens();
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
          className={`${buttonClass("ghost", size)} text-foreground`}
        >
          {t("signOut")}
        </button>
      </>
    );
  }

  return (
    <>
      <Link href="/signin" className={`${buttonClass("ghost", size)} text-foreground`}>
        {tn("signIn")}
      </Link>
      <ButtonLink href="/signin" size={size}>
        {tn("getStarted")}
      </ButtonLink>
    </>
  );
}
