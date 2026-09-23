/**
 * Where a person should land, and the one piece of history that decides it.
 *
 * One identity can hold a job-seeker profile and several organisations
 * (ADR-038). Signing in used to answer "where now?" by sending anyone with a
 * personal membership to `/matches` -- so the central case, a candidate who
 * also hires, was always resolved in favour of the job seeker -- and by taking
 * `.find()` over `memberships`, which the API returns in no particular order,
 * so a two-organisation account landed in whichever one Postgres listed first.
 *
 * The last context someone used is remembered here. It is a preference, not an
 * authority: context is still derived from the URL and granted by membership,
 * so a remembered slug is honoured only if it is one of *this* account's
 * organisations. That is also what makes it safe on a shared phone.
 */

const LAST = "iism.last_context";

/**
 * The last few contexts used, most recent first.
 *
 * Kept beside `LAST` rather than replacing it, so `landingFor` keeps its exact
 * meaning and its tests keep their exact subject: landing is about **one**
 * answer, and this is about **ordering a list**. The switcher uses it so that
 * somebody holding ten organisations finds the two they actually move between
 * at the top, instead of scanning an alphabetical wall every time.
 */
const RECENT = "iism.recent_contexts";

/** How many to remember. Beyond a handful it stops being recency and starts
 *  being a second copy of the list, which is what the filter box is for. */
const RECENT_LIMIT = 5;

/** The job-seeker context. Organisations are remembered by slug. */
export const SEEKER = "seeker";

type MembershipLike = { tenant: { slug: string; tenant_type: string } };

function safe<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    // Private browsing and blocked site data both throw on access.
    return fallback;
  }
}

export function rememberContext(context: string): void {
  safe(() => localStorage.setItem(LAST, context), undefined);
  safe(() => {
    const kept = recentContexts().filter((c) => c !== context);
    localStorage.setItem(
      RECENT,
      JSON.stringify([context, ...kept].slice(0, RECENT_LIMIT)),
    );
  }, undefined);
}

/**
 * The contexts this browser has used, most recent first.
 *
 * Returns `[]` rather than throwing on anything unexpected -- a corrupted or
 * hand-edited value is a reason to fall back to alphabetical order, never a
 * reason for the header to fail to render.
 */
export function recentContexts(): string[] {
  return safe(() => {
    const raw = localStorage.getItem(RECENT);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((c): c is string => typeof c === "string")
      : [];
  }, []);
}

export function lastContext(): string | null {
  return safe(() => localStorage.getItem(LAST), null);
}

export function forgetContext(): void {
  safe(() => localStorage.removeItem(LAST), undefined);
  // Signing out clears this too. It is a list of organisation slugs, which on
  // a shared phone says who the previous person worked for.
  safe(() => localStorage.removeItem(RECENT), undefined);
}

/**
 * The path to send someone to after they sign in.
 *
 * In order: the organisation this sign-in was explicitly *for* (the API names
 * it when it has just created one); then whatever they last used, if they still
 * hold it; then the job-seeker side if they have one; then their first
 * organisation by slug, which is at least the same answer every time.
 */
export function landingFor(
  memberships: MembershipLike[],
  {
    organisationSlug = null,
    last = null,
  }: { organisationSlug?: string | null; last?: string | null } = {},
): string {
  const organisations = memberships
    .filter((m) => m.tenant.tenant_type !== "personal")
    .map((m) => m.tenant.slug)
    .sort();
  const isJobSeeker = memberships.some(
    (m) => m.tenant.tenant_type === "personal",
  );

  if (organisationSlug && organisations.includes(organisationSlug))
    return `/employer/${organisationSlug}`;
  if (last === SEEKER && isJobSeeker) return "/matches";
  if (last && organisations.includes(last)) return `/employer/${last}`;
  if (isJobSeeker) return "/matches";
  if (organisations.length > 0) return `/employer/${organisations[0]}`;
  return "/";
}
