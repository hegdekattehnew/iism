"use client";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { currentHref } from "@/lib/nav";
import { useUnreadCount } from "@/lib/unread-count";
import { useIsSignedIn } from "@/lib/auth";

const HREFS = [
  "/matches",
  "/applications",
  "/saved",
  "/notifications",
  "/profile",
  "/interests",
  "/career-paths",
  "/account",
] as const;

/**
 * The strip of a job seeker's own pages (`CandidateNav` fetches it and holds its place).
 *
 * It scrolls sideways on a phone, so a long label in Hindi does not wrap the page; the current page
 * is `aria-current` and filled. The unread count is drawn in the corner of its tab, out of the flow,
 * so it arriving moves nothing, and is spoken once in words.
 */
export function CandidateStrip() {
  const pathname = usePathname();
  const signedIn = useIsSignedIn();
  const unread = useUnreadCount(signedIn);
  const ta = useTranslations("auth");
  const tap = useTranslations("applications");
  const labels: Record<(typeof HREFS)[number], string> = {
    "/matches": ta("myMatches"),
    "/applications": tap("navApplications"),
    "/saved": tap("savedPageTitle"),
    "/notifications": useTranslations("notificationsPage")("title"),
    "/profile": useTranslations("profilePage")("title"),
    "/interests": useTranslations("courseInterest")("pageTitle"),
    "/career-paths": useTranslations("careerPaths")("title"),
    "/account": ta("account"),
  };
  const tn = useTranslations("nav");
  const current = currentHref(HREFS, pathname);

  return (
    <nav aria-label={tn("candidateLabel")} className="-mx-5 overflow-x-auto px-5">
      <ul className="flex min-w-max gap-2 pb-1">
        {HREFS.map((href) => {
          const here = href === current;
          const count = href === "/notifications" ? unread : 0;
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={here ? "page" : undefined}
                className={`relative inline-flex min-h-11 items-center whitespace-nowrap rounded-full border px-4 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                  here
                    ? "border-brand bg-accent-tint text-accent-text"
                    : "border-border-token bg-surface text-foreground hover:bg-surface-muted"
                }`}
              >
                {labels[href]}
                {count > 0 && (
                  <>
                    <span
                      aria-hidden
                      className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-danger-solid px-1 text-2xs font-bold text-white"
                    >
                      {count > 99 ? "99+" : count}
                    </span>
                    <span className="sr-only">{ta("updatesUnread", { count })}</span>
                  </>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
