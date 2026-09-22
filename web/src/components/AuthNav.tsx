"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";

import { useActiveOrg } from "@/components/ContextSwitcher";
import { ButtonLink, buttonVariants } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { clearTokens, getRefreshToken, useIsSignedIn } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { forgetContext } from "@/lib/context";
import { useMemberships } from "@/lib/org";
import { useDismiss } from "@/lib/use-dismiss";

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
 *
 * **One visible action, and a menu for the rest.** Sprint 26 counted ten
 * controls in a single flat header row, three of which were account plumbing
 * and one of which -- "My matches" -- was a filled brand button competing with
 * whatever the page's own primary action was. A brand fill should mean one
 * thing per screen. The destinations are unchanged; only how many of them
 * shout at once.
 *
 * `stacked` (the mobile nav) keeps the flat list: a dropdown inside an
 * already-expanded menu is a second thing to open for no gain, and on a phone
 * the row is not competing for space with anything.
 */
export function AuthNav({ stacked = false }: { stacked?: boolean }) {
  const t = useTranslations("auth");
  const tn = useTranslations("nav");
  const ta = useTranslations("applications");
  const router = useRouter();
  const qc = useQueryClient();
  const signedIn = useIsSignedIn();
  const active = useActiveOrg();
  const { organisations, isJobSeeker, isPending } = useMemberships();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useDismiss(
    menuRef,
    menuOpen,
    useCallback(() => setMenuOpen(false), []),
  );

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

    // The one destination worth a button. Everything else is in the menu.
    const primary = isPending ? null : inOrg ? (
      <ButtonLink href={`/employer/${active}/settings`} variant="secondary" size={size}>
        {t("orgProfile")}
      </ButtonLink>
    ) : isJobSeeker ? (
      <ButtonLink href="/matches" variant="secondary" size={size}>
        {t("myMatches")}
      </ButtonLink>
    ) : onlyOrg ? (
      <ButtonLink href={`/employer/${onlyOrg.tenant.slug}`} variant="secondary" size={size}>
        {t("myWorkspace")}
      </ButtonLink>
    ) : null;

    // The job-seeker destinations, offered only to an account that asked to
    // look for work and only outside an organisation -- the rule this
    // component exists to keep.
    const seekerItems =
      !isPending && !inOrg && isJobSeeker
        ? [
            { href: "/applications", label: ta("navApplications") },
            { href: "/profile", label: t("myProfile") },
          ]
        : [];

    if (stacked) {
      // Mobile: the flat list, unchanged.
      return (
        <>
          {primary}
          {seekerItems.map((i) => (
            <ButtonLink key={i.href} href={i.href} variant="secondary" size={size}>
              {i.label}
            </ButtonLink>
          ))}
          <Link
            href="/account"
            className={cn(buttonVariants({ variant: "ghost", size }), "text-foreground")}
          >
            {t("account")}
          </Link>
          <button
            type="button"
            onClick={() => void signOut()}
            className={cn(buttonVariants({ variant: "ghost", size }), "text-foreground")}
          >
            {t("signOut")}
          </button>
        </>
      );
    }

    return (
      <>
        {primary}
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            className={cn(buttonVariants({ variant: "ghost", size }), "text-foreground")}
          >
            {t("account")}
          </button>
          {menuOpen && (
            // A disclosure, not an ARIA `menu`. `role="menu"` promises
            // arrow-key navigation and typeahead, and an `<a role="menuitem">`
            // stops being a link to assistive technology -- which is both a
            // worse experience for a list of destinations and a promise this
            // component does not keep. Plain links in a revealed panel.
            <div className="absolute right-0 z-50 mt-2 w-56 rounded-lg border border-border-token bg-surface p-1 shadow-raised">
              {seekerItems.map((i) => (
                <Link
                  key={i.href}
                  href={i.href}
                  onClick={() => setMenuOpen(false)}
                  className="block rounded-md px-3 py-2 text-sm hover:bg-surface-muted"
                >
                  {i.label}
                </Link>
              ))}
              {/* Every signed-in account, whatever it holds: the DPDP rights --
                  download, delete, see what was agreed -- belong to the person. */}
              <Link
                href="/account"
                onClick={() => setMenuOpen(false)}
                className="block rounded-md px-3 py-2 text-sm hover:bg-surface-muted"
              >
                {t("accountSettings")}
              </Link>
              <button
                type="button"
                onClick={() => void signOut()}
                className="block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-surface-muted"
              >
                {t("signOut")}
              </button>
            </div>
          )}
        </div>
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
