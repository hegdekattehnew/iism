"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { AuthNav } from "@/components/AuthNav";
import { ContextSwitcher, useActiveOrg } from "@/components/ContextSwitcher";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { Logo } from "@/components/ui";
import { Link, usePathname } from "@/i18n/navigation";
import { SEEKER, rememberContext } from "@/lib/context";
import { currentHref, isReducedHeader } from "@/lib/nav";
import { useDismiss } from "@/lib/use-dismiss";
import { useOrgDelivers, useOrgType } from "@/lib/org";

/** What a job seeker is here to do. Also what an anonymous visitor sees. */
const SEEKER_NAV = [
  { key: "jobs", href: "/jobs" },
  { key: "courses", href: "/courses" },
  { key: "skills", href: "/skills" },
  { key: "howItWorks", href: "/#how-it-works" },
] as const;

/** What each kind of organisation is here to do. The navigation changes with the
 *  context, not just the page -- otherwise "switching" would mean nothing more
 *  than going somewhere that happens to be an organisation.
 *
 *  A training provider used to be shown "Vacancies", which is not a thing they
 *  can have.
 *
 *  The organisation's profile is not here: it is the header's *profile* control
 *  (`AuthNav`), in the slot "My profile" occupies for a job seeker, so the same
 *  place means the same thing in every context. */
const ORG_NAV = {
  employer: [
    { key: "vacancies", href: "" },
    { key: "team", href: "/team" },
  ],
  // A provider gains a third item because their inbox is not reachable
  // through a vacancy the way an employer's is -- they have no vacancies.
  course_provider: [
    { key: "courses_org", href: "" },
    { key: "learners", href: "/interests" },
    { key: "delivery", href: "/delivery" },
    { key: "team", href: "/team" },
  ],
  // A centre's manager has one page: their centre (Sprint 96). No team, no vacancies, no courses.
  training_centre: [{ key: "centre", href: "" }],
} as const;

export function Header() {
  const t = useTranslations("nav");
  const [open, setOpen] = useState(false);
  const activeOrg = useActiveOrg();
  const orgType = useOrgType(activeOrg);
  const delivers = useOrgDelivers(activeOrg);
  const pathname = usePathname();
  const headerRef = useRef<HTMLElement>(null);
  const closeNav = useCallback(() => setOpen(false), []);
  // Escape, or a tap outside the header, closes the mobile menu (it only ever closed by its own button).
  useDismiss(headerRef, open, closeNav);
  // Inside an organisation, its nav -- once we know what kind it is. The old
  // fallback, `ORG_NAV[orgType ?? "employer"]`, showed a training provider
  // "Vacancies" on every first paint, because `orgType` is null until
  // `/auth/me` resolves. The same fix `ContextSwitcher` already made: show
  // nothing rather than something wrong.
  const nav: { key: string; href: string }[] = activeOrg
    ? orgType
      ? [
          ...ORG_NAV[orgType],
          // An organisation that delivers training has centres (Sprint 95); one that only sells
          // courses has no such page, so it is not offered. Only a training organisation can
          // deliver (the server refuses an employer that does), so `delivers` is the whole test.
          ...(delivers
            ? [{ key: "centres", href: "/centres" }]
            : []),
        ].map(({ key, href }) => ({
          key,
          href: `/employer/${activeOrg}${href}`,
        }))
      : []
    : SEEKER_NAV.map(({ key, href }) => ({ key, href }));

  // Remember which side of the account was last used, so signing in lands a
  // dual-role person where they left off instead of always on `/matches`.
  // A preference, not an authority -- see `lib/context.ts`.
  useEffect(() => {
    if (activeOrg) rememberContext(activeOrg);
    else if (/^\/(matches|profile)(\/|$)/.test(pathname)) rememberContext(SEEKER);
  }, [activeOrg, pathname]);
  // Closed on click rather than in an effect keyed to the path: the effect form
  // sets state during render-commit, which React 19 flags.
  const close = closeNav;
  // The page the person is on, in the navigation (`aria-current`, and drawn so).
  const current = currentHref(
    nav.map((n) => n.href),
    pathname,
  );

  // Signing in or up: the logo to go back, the language, and nothing else to leave for (Sprint 81).
  const reduced = isReducedHeader(pathname);

  return (
    <header
      ref={headerRef}
      className="sticky top-0 z-50 border-b border-border-token bg-background/85 backdrop-blur"
    >
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-5">
        <Link href="/" aria-label="IISM" className="inline-flex min-h-11 shrink-0 items-center">
          <Logo />
        </Link>

        {!reduced && (
          <nav className="hidden items-center gap-1 lg:flex" aria-label="Main">
            {nav.map(({ key, href }) => (
              <Link
                key={key}
                href={href}
                aria-current={href === current ? "page" : undefined}
                className={`inline-flex min-h-11 items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-surface-muted hover:text-foreground ${
                  href === current ? "bg-accent-soft text-foreground" : "text-muted"
                }`}
              >
                {t(key)}
              </Link>
            ))}
          </nav>
        )}

        {reduced ? (
          <LocaleSwitcher />
        ) : (
          <div className="hidden items-center gap-2 lg:flex">
            <ContextSwitcher />
            <LocaleSwitcher />
            <AuthNav />
          </div>
        )}

        {!reduced && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? t("closeMenu") : t("openMenu")}
            className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-border-token lg:hidden"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              {open ? (
                <path d="M6 6l12 12M18 6L6 18" />
              ) : (
                <path d="M4 7h16M4 12h16M4 17h16" />
              )}
            </svg>
          </button>
        )}
      </div>

      {open && !reduced && (
        <div
          id="mobile-nav"
          className="max-h-[calc(100dvh-4rem)] overflow-y-auto border-t border-border-token bg-background lg:hidden"
        >
          <nav
            className="mx-auto flex max-w-6xl flex-col gap-1 px-5 py-4"
            aria-label="Main"
          >
            {nav.map(({ key, href }) => (
              <Link
                key={key}
                href={href}
                onClick={close}
                aria-current={href === current ? "page" : undefined}
                className={`flex min-h-12 items-center rounded-lg px-3 py-2.5 text-base font-medium text-foreground hover:bg-surface-muted ${
                  href === current ? "bg-accent-soft" : ""
                }`}
              >
                {t(key)}
              </Link>
            ))}
            <div className="mt-3 border-t border-border-token pt-4">
              <ContextSwitcher stacked />
            </div>
            <div
              onClick={close}
              className="mt-3 flex flex-col gap-2 border-t border-border-token pt-4"
            >
              <AuthNav stacked />
              <div className="pt-2">
                <LocaleSwitcher />
              </div>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
