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

type TenantType = "personal" | "employer" | "course_provider";

export type TestMembership = {
  role: string;
  tenant: { slug: string; name: string; tenant_type: TenantType };
};

export const world = {
  pathname: "/",
  signedIn: true,
  pending: false,
  memberships: [] as TestMembership[],
  push: vi.fn(),
};

/** Reset between tests; each test then states only what it cares about. */
export function resetWorld(): void {
  world.pathname = "/";
  world.signedIn = true;
  world.pending = false;
  world.memberships = [];
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
  const memberships = world.pending ? [] : world.memberships;
  return {
    data: world.pending
      ? undefined
      : { memberships, full_name: null, phone: "+919812349999", email: null },
    isPending: world.pending,
    isError: false,
    memberships,
    organisations: memberships.filter((m) => m.tenant.tenant_type !== "personal"),
    isJobSeeker: memberships.some((m) => m.tenant.tenant_type === "personal"),
  };
}

export const orgMock = {
  useMemberships: derived,
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
