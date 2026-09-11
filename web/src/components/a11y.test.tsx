import axe from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AccountPanel } from "@/components/AccountPanel";
import { AuthNav } from "@/components/AuthNav";
import { SignInForm } from "@/components/SignInForm";
import { SignUpForm } from "@/components/SignUpForm";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

beforeEach(resetWorld);

/**
 * Automated accessibility checks over the forms a person must get through.
 *
 * axe catches the mechanical failures -- an input with no label, a button with
 * no name, a duplicate id, ARIA that points nowhere -- which are exactly the
 * ones nobody notices with a mouse. Colour contrast is off because jsdom has no
 * layout or computed colours: it would pass everything and prove nothing. The
 * input-border contrast is set in `globals.css` and measured there instead.
 */
async function violations(container: HTMLElement) {
  const results = await axe.run(container, {
    rules: { "color-contrast": { enabled: false } },
  });
  return results.violations.map(
    (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
  );
}

describe("accessibility — the check itself", () => {
  it("does report a violation when there is one", async () => {
    // Without this, a misconfigured axe (no rules run, wrong container) would
    // pass every test below while checking nothing.
    const { container } = renderUi(<input type="text" />);
    expect((await violations(container)).join()).toMatch(/^label:/);
  });
});

describe("accessibility — the ways in", () => {
  it.each(["seeker", "employer", "provider"] as const)(
    "signup as %s",
    async (type) => {
      world.signedIn = false;
      const { container } = renderUi(<SignUpForm type={type} />);
      expect(await violations(container)).toEqual([]);
    },
  );

  it("sign in", async () => {
    world.signedIn = false;
    const { container } = renderUi(<SignInForm />);
    expect(await violations(container)).toEqual([]);
  });
});

describe("accessibility — signed in", () => {
  it("the header controls", async () => {
    world.memberships = [personal(), org("tnt")];
    const { container } = renderUi(
      <nav aria-label="Account">
        <AuthNav />
      </nav>,
    );
    expect(await violations(container)).toEqual([]);
  });

  it("the account page", async () => {
    world.memberships = [personal()];
    const { container } = renderUi(<AccountPanel />);
    expect(await violations(container)).toEqual([]);
  });
});
