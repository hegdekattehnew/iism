import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplyPanel } from "@/components/ApplyPanel";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

beforeEach(resetWorld);

const panel = () => <ApplyPanel jobSlug="cashier-bengaluru" organisation="Apply Co" />;

describe("ApplyPanel — who is offered the button", () => {
  it("asks a signed-out visitor to sign in, rather than failing later", () => {
    world.signedIn = false;
    renderUi(panel());
    expect(
      screen.getByRole("link", { name: "Sign in to apply" }).getAttribute("href"),
    ).toBe("/signin");
    expect(screen.queryByRole("button", { name: /Apply/ })).toBeNull();
  });

  it("offers a job seeker the button", () => {
    world.memberships = [personal()];
    renderUi(panel());
    expect(screen.getByRole("button", { name: "Apply for this job" })).toBeTruthy();
  });

  it("offers an organisation-only account nothing at all", () => {
    // `get_current_candidate` refuses this account, so a button here would be
    // an affordance that always fails.
    world.memberships = [org("tnt")];
    const { container } = renderUi(panel());
    expect(screen.queryByRole("button")).toBeNull();
    expect(container.textContent).toBe("");
  });

  it("renders nothing while it does not yet know which kind of account this is", () => {
    world.pending = true;
    const { container } = renderUi(panel());
    expect(container.textContent).toBe("");
  });
});

describe("ApplyPanel — the confirm step is the consent moment", () => {
  it("names what is shared, with whom, and that withdrawing takes it back", () => {
    world.memberships = [personal()];
    renderUi(panel());
    fireEvent.click(screen.getByRole("button", { name: "Apply for this job" }));

    // The disclosure in full, before the act that makes it.
    expect(
      screen.getByText(
        /sends your name, mobile number and email to Apply Co, for this vacancy only/,
      ),
    ).toBeTruthy();
    expect(screen.getByText(/they stop seeing your contact details/)).toBeTruthy();
    // Nothing is pre-ticked, and the button that discloses says so.
    expect(screen.getByRole("button", { name: "Yes, apply" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeTruthy();
  });
});
