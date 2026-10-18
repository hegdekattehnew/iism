/**
 * Where a person is, in the navigation (Sprint 81, BL-19.13, ADR-090). Pure, so the rules are tested
 * without a browser; `Header`, `CandidateNav` and `MobileTabBar` all ask it.
 */

/** Pages whose header is only the logo and the language: the person is in the middle of signing in. */
const REDUCED_HEADER = /^\/(signin|signup|employers\/signin)(\/|$)/;

/** Whether this page gets the reduced header. `pathname` has no locale prefix (the i18n `usePathname`). */
export function isReducedHeader(pathname: string): boolean {
  return REDUCED_HEADER.test(pathname);
}

/** Pages with no bottom tab bar: an organisation's workspace, the back office, and signing in. */
const NO_TAB_BAR = /^\/(employer|admin|signin|signup|employers\/signin)(\/|$)/;

export function showsTabBar(pathname: string): boolean {
  return !NO_TAB_BAR.test(pathname);
}

/**
 * Which of these links is the page the person is on: the **longest** one that is the path or a parent
 * of it. A parent counts (`/employer/acme/jobs/x/applications` is the vacancies page's), and when two
 * nest the deeper wins (`/employer/acme/team` is the team's, not the vacancies'). A link to nowhere is
 * never current, nor is one to a place in a page (`/#how-it-works`): a pathname has no hash, so it
 * can never equal one.
 */
export function currentHref(hrefs: readonly string[], pathname: string): string | null {
  let best: string | null = null;
  for (const href of hrefs) {
    if (!href) continue;
    if (pathname === href || pathname.startsWith(`${href}/`)) {
      if (best === null || href.length > best.length) best = href;
    }
  }
  return best;
}

/** The four places a job seeker goes most, as the bottom bar on a phone's browser (the owner's choice, BL-19.2). */
export const TAB_ITEMS = [
  { key: "jobs", href: "/jobs" },
  { key: "courses", href: "/courses" },
  { key: "tabMatches", href: "/matches" },
  { key: "tabProfile", href: "/profile" },
] as const;
