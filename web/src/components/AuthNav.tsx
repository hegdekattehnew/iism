"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { useActiveOrg } from "@/components/ContextSwitcher";
import { ButtonLink, buttonVariants } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { clearTokens, getRefreshToken, useIsSignedIn } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { forgetContext } from "@/lib/context";
import { useMemberships } from "@/lib/org";

/**
 * Header auth controls. Rendered client-side, because whether someone is
 * signed in is only knowable in the browser.
 *
 * **Signed in, the "profile" slot follows the context the person is standing
 * in.** It used to render "My matches" and "My profile" for every signed-in
 * identity, unconditionally -- so inside `/employer/tnt` the header showed the
 * organisation's nav in the middle and the job seeker's buttons on the right,
 * and "My profile" took an organisation owner to the candidate editor. This was
 * the only signed-in header component that never asked what the account holds.
 *
 * Inside an organisation you belong to: that organisation's profile. Outside
 * one: matches and profile, but only for an account that signed up to look for
 * work. An organisation-only account never sees the job-seeker side.
 */
export function AuthNav({ stacked = false }: { stacked?: boolean }) {
  const t = useTranslations("auth");
  const tn = useTranslations("nav");
  const router = useRouter();
  const qc = useQueryClient();
  const signedIn = useIsSignedIn();
  const active = useActiveOrg();
  const { organisations, isJobSeeker, isPending } = useMemberships();

  const signOut = async () => {
    const refresh_token = getRefreshToken();
    // Revoke server-side first; clearing locally alone would leave a valid
    // refresh token in play for 30 days.
    if (refresh_token)
      await api.POST("/auth/logout", { body: { refresh_token } });
    clearTokens();
    forgetContext();
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
    // Standing in an organisation this account actually belongs to. A slug in
    // the URL alone is not enough -- the page will say "no access".
    const inOrg =
      active !== null && organisations.some((m) => m.tenant.slug === active);
    const onlyOrg = organisations.length === 1 ? organisations[0] : null;

    return (
      <>
        {/* Nothing while `/auth/me` is in flight: an empty slot for a moment is
            better than the wrong person's buttons for a moment. */}
        {isPending ? null : inOrg ? (
          <ButtonLink
            href={`/employer/${active}/settings`}
            variant="secondary"
            size={size}
          >
            {t("orgProfile")}
          </ButtonLink>
        ) : isJobSeeker ? (
          <>
            <ButtonLink href="/matches" size={size}>
              {t("myMatches")}
            </ButtonLink>
            <ButtonLink href="/profile" variant="secondary" size={size}>
              {t("myProfile")}
            </ButtonLink>
          </>
        ) : onlyOrg ? (
          <ButtonLink href={`/employer/${onlyOrg.tenant.slug}`} size={size}>
            {t("myWorkspace")}
          </ButtonLink>
        ) : null}
        {/* Every signed-in account, whatever it holds: the DPDP rights --
            download, delete, see what was agreed -- belong to the person. */}
        <Link
          href="/account"
          className={cn(
            buttonVariants({ variant: "ghost", size }),
            "text-foreground",
          )}
        >
          {t("account")}
        </Link>
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
