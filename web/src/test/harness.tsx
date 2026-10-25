/**
 * The seams these tests control, and one way to render through them.
 *
 * What varies between the defects is **who is signed in, what they hold, and
 * which URL they are on**. Those three come from `@/lib/auth`, `@/lib/org` and
 * `@/i18n/navigation`, so each test file mocks exactly those three modules with
 * the factories below and sets `world` per test. Everything else -- next-intl,
 * TanStack Query, the component library -- is the real thing.
 *
 * Usage, at the top of a test file (vitest hoists `vi.mock` above imports):
 *
 *   vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
 *   vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
 *   vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactElement, ReactNode } from "react";
import { vi } from "vitest";

import messages from "@/messages/en.json";

type TenantType = "personal" | "employer" | "course_provider" | "training_centre";

export type TestMembership = {
  role: string;
  tenant: {
    slug: string;
    name: string;
    tenant_type: TenantType;
    // What a training organisation does (Sprint 94/95); absent on every other kind.
    delivers_training?: boolean;
    publishes_courses?: boolean;
  };
};

export const world = {
  pathname: "/",
  signedIn: true,
  pending: false,
  // A sign-in the server refuses (an expired or revoked token): the token is still stored, so the
  // browser reads as signed in, but `/auth/me` answered an error (Sprint 91).
  meError: false,
  // Operator authority (ADR-042). Global, granted by nothing a membership can
  // give, so it is a field of its own rather than a role in `memberships`.
  isStaff: false,
  // The operator's tier (ADR-044): `support` or `admin`. Only read where a control is tier-gated.
  staffTier: "admin" as string | null,
  memberships: [] as TestMembership[],
  // How this person signs in (Sprint 56): what `/auth/me` says about the two credentials.
  account: {
    phone: "+919812349999" as string | null,
    email: null as string | null,
    phone_verified_at: "2026-01-01T00:00:00Z" as string | null,
    email_verified_at: null as string | null,
    // Consent (Sprint 72): by default somebody who agreed to the notice in force.
    consent_version: "2026-10-24" as string | null,
    consent_current: true,
    consent_withdrawn: false,
  },
  push: vi.fn(),
};

/** Reset between tests; each test then states only what it cares about. */
export function resetWorld(): void {
  world.pathname = "/";
  world.signedIn = true;
  world.pending = false;
  world.meError = false;
  world.isStaff = false;
  world.staffTier = "admin";
  world.memberships = [];
  world.account = {
    phone: "+919812349999",
    email: null,
    phone_verified_at: "2026-01-01T00:00:00Z",
    email_verified_at: null,
    consent_version: "2026-10-24",
    consent_current: true,
    consent_withdrawn: false,
  };
  world.push = vi.fn();
}

export const personal = (): TestMembership => ({
  role: "owner",
  tenant: { slug: "personal-abc123", name: "Personal workspace", tenant_type: "personal" },
});

export const org = (
  slug: string,
  tenant_type: TenantType = "employer",
  name = slug,
): TestMembership => ({ role: "owner", tenant: { slug, name, tenant_type } });

// ---------------------------------------------------------------- the mocks

export const authMock = {
  useIsSignedIn: () => world.signedIn,
  getAccessToken: () => (world.signedIn ? "token" : null),
  getRefreshToken: () => null,
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  onAuthChange: () => () => {},
};

function derived() {
  // Signed out means `/auth/me` answered 401, so the query has no data and is
  // in error -- not "an account with no memberships". The two were the same
  // here until Sprint 29, which made every signed-out branch untestable
  // through this seam: a component reading `me.data` saw a populated account
  // for somebody who was not signed in.
  const signedOut = !world.signedIn || world.meError;
  const memberships = world.pending || signedOut ? [] : world.memberships;
  return {
    data:
      world.pending || signedOut
        ? undefined
        : {
            memberships,
            full_name: null,
            ...world.account,
            is_staff: world.isStaff,
            staff_tier: world.staffTier,
          },
    isPending: world.pending,
    isError: signedOut,
    memberships,
    organisations: memberships.filter((m) => m.tenant.tenant_type !== "personal"),
    isJobSeeker: memberships.some((m) => m.tenant.tenant_type === "personal"),
  };
}

export const orgMock = {
  useMemberships: derived,
  useOrgSells: (slug: string | null) => {
    if (!slug) return false;
    const found = derived().organisations.find((m) => m.tenant.slug === slug);
    return found?.tenant.publishes_courses === true;
  },
  useOrgDelivers: (slug: string | null) => {
    if (!slug) return false;
    const found = derived().organisations.find((m) => m.tenant.slug === slug);
    return found?.tenant.delivers_training === true;
  },
  useOrgType: (slug: string | null) => {
    if (!slug) return null;
    const found = derived().organisations.find((m) => m.tenant.slug === slug);
    return found ? found.tenant.tenant_type : null;
  },
};

function Link({
  href,
  children,
  replace,
  ...rest
}: AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
  children: ReactNode;
  replace?: boolean;
}) {
  // `replace` is a navigation option, not an anchor attribute; forwarding it
  // makes React warn about a non-boolean attribute on <a>.
  void replace;
  return (
    <a href={href} {...rest}>
      {children}
    </a>
  );
}

export const navigationMock = {
  Link,
  usePathname: () => world.pathname,
  useRouter: () => ({ push: world.push, replace: vi.fn() }),
  redirect: vi.fn(),
  getPathname: ({ href }: { href: string }) => href,
};

// ------------------------------------------------------------------ render

/**
 * A missing message key **fails the test**.
 *
 * next-intl's default is to log and render the key path itself, which is how
 * `employerConsole.matchScore` reached the employer's inbox and sat there
 * looking like a label until someone read the screen. The inbox asked for it in
 * the console's namespace; it only ever existed in the candidate's. It compiled,
 * `tsc` was clean, and no test rendered the component.
 *
 * Throwing here makes every test in this suite a guard against that, not only
 * the ones written to look for it.
 */
function onIntlError(error: Error & { code?: string }): void {
  // Only a missing key. Every other next-intl error is about the environment
  // this renderer runs in -- jsdom has no ambient time zone, for one -- and
  // turning those into failures would say nothing about the product.
  if (error.code === "MISSING_MESSAGE") throw error;
}

export function renderUi(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider
        locale="en"
        messages={messages}
        // Pinned, not the machine's: a formatted date must not depend on where
        // the test happens to run. India-first, so India's zone.
        timeZone="Asia/Kolkata"
        onError={onIntlError}
      >
        {ui}
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}
