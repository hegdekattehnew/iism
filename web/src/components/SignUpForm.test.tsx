import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignUpForm } from "@/components/SignUpForm";
import { personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: vi.fn(),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

beforeEach(() => {
  resetWorld();
  POST.mockReset();
});

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

describe("SignUpForm — consent is asked for, and cannot be skipped", () => {
  it.each(["seeker", "employer", "provider"] as const)(
    "a stranger signing up as %s must tick the notice before a code is sent",
    (type) => {
      // DPDP Act 2023: consent has to be given before processing starts, and
      // `required` is what stops the form submitting without it.
      world.signedIn = false;
      renderUi(<SignUpForm type={type} />);

      const box = screen.getByRole("checkbox", { name: /privacy notice/ });
      expect(box).toHaveProperty("required", true);
      expect(
        screen.getByRole("link", { name: "privacy notice" }).getAttribute("href"),
      ).toBe("/privacy");
      expect(
        screen.getByRole("link", { name: "terms of use" }).getAttribute("href"),
      ).toBe("/terms");
    },
  );

  it("asks nothing of someone already signed in", () => {
    // They agreed when their account was made; adding an organisation to it
    // is not a new data subject.
    world.memberships = [personal()];
    renderUi(<SignUpForm type="employer" />);
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});

describe("SignUpForm — the same endpoint, told the same way on both screens", () => {
  /**
   * `POST /me/organisations` has two callers. `CreateOrgForm` reads the status
   * and names a duplicate name and a hit rate cap; this one threw
   * `new Error("create failed")` and showed one generic line for both -- the
   * verbatim string CLAUDE.md records as the origin of the "[object Object]"
   * defect. Two paths to one endpoint should not disagree about what it said.
   */
  const create = async (status: number) => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "no" },
      response: { status, headers: new Headers() },
    });
    world.memberships = [personal()];
    renderUi(<SignUpForm type="employer" />);
    fireEvent.change(input("Sunrise Multispeciality Hospital") as HTMLElement, {
      target: { value: "Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
  };

  it("names a duplicate organisation name", async () => {
    await create(409);
    expect(
      await screen.findByText("You already have an organisation with that name."),
    ).toBeTruthy();
  });

  it("names the daily cap rather than calling it a generic failure", async () => {
    await create(429);
    expect(await screen.findByText(/created a lot of organisations today/)).toBeTruthy();
  });

  it("keeps the generic line for a failure it cannot name", async () => {
    await create(500);
    expect(
      await screen.findByText("Could not create the organisation. Try again."),
    ).toBeTruthy();
  });
});
