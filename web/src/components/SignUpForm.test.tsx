import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignUpForm } from "@/components/SignUpForm";
import { personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

beforeEach(resetWorld);

const input = (placeholder: string) =>
  screen.queryByPlaceholderText(placeholder);

describe("SignUpForm — a signed-in person is never offered a second account", () => {
  it("adds the organisation to the account they are in, with no email", () => {
    // Cold registration with a fresh email minted a second `User` -- the
    // fork ADR-038 exists to prevent.
    world.memberships = [personal()];
    renderUi(<SignUpForm type="employer" />);

    expect(screen.queryByRole("textbox", { name: "Work email" })).toBeNull();
    expect(input("Sunrise Multispeciality Hospital")).not.toBeNull();
    expect(
      screen.getByText(/Added to the account you are signed in as/),
    ).toBeTruthy();
  });

  it("offers a signed-in job seeker the way on, not a phone form", () => {
    world.memberships = [personal()];
    renderUi(<SignUpForm type="seeker" />);

    expect(input("98765 43210")).toBeNull();
    expect(screen.getByText("You are already signed in.")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Continue" }).getAttribute("href"),
    ).toBe("/matches");
  });
});

describe("SignUpForm — a stranger is told up front what an existing number does", () => {
  it("asks a stranger for a work email", () => {
    world.signedIn = false;
    renderUi(<SignUpForm type="employer" />);

    expect(
      screen.getByText(/Already registered with this address\?/),
    ).toBeTruthy();
  });

  it("tells a stranger an existing number simply signs them in", () => {
    // Said before the request, because the request cannot say it.
    world.signedIn = false;
    renderUi(<SignUpForm type="seeker" />);

    expect(input("98765 43210")).not.toBeNull();
    expect(
      screen.getByText(/Already registered with this number\?/),
    ).toBeTruthy();
  });
});
