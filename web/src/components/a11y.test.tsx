import axe from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AccountPanel } from "@/components/AccountPanel";
import { ApplyPanel } from "@/components/ApplyPanel";
import { AuthNav } from "@/components/AuthNav";
import { CreateOrgForm } from "@/components/CreateOrgForm";
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

  it("the apply panel, and its confirm step", async () => {
    world.memberships = [personal()];
    const { container } = renderUi(
      <ApplyPanel jobSlug="cashier-bengaluru" organisation="Apply Co" />,
    );
    expect(await violations(container)).toEqual([]);
  });

  it("the account page", async () => {
    world.memberships = [personal()];
    const { container } = renderUi(<AccountPanel />);
    expect(await violations(container)).toEqual([]);
  });
});

describe("accessibility — the modal dialog", () => {
  it("is a labelled, described dialog with nothing axe objects to", async () => {
    // Sprint 26's dialog claimed `aria-modal="true"` and never moved focus,
    // locked scroll or handled Escape. The primitive under it now does all
    // three; this is the mechanical half -- that it is named, described and
    // wired correctly.
    //
    // **The container is `document.body`, not the render container.** The
    // dialog portals out, so scanning the render container would scan an
    // empty div and report nothing wrong with a screen it never saw.
    renderUi(<CreateOrgForm onClose={() => {}} onCreated={() => {}} />);
    expect(await violations(document.body)).toEqual([]);
  });
});
