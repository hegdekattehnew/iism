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
}

export function lastContext(): string | null {
  return safe(() => localStorage.getItem(LAST), null);
}

export function forgetContext(): void {
  safe(() => localStorage.removeItem(LAST), undefined);
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
