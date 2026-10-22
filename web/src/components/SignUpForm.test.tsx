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

describe("SignUpForm — what a training organisation does (ADR-102)", () => {
  const caps = () => screen.queryByRole("group", { name: "What does your organisation do?" });

  it("asks a stranger signing up as a provider, and nobody else", () => {
    world.signedIn = false;
    const a = renderUi(<SignUpForm type="provider" />);
    expect(caps()).not.toBeNull();
    a.unmount();
    renderUi(<SignUpForm type="employer" />);
    expect(caps()).toBeNull();
  });

  it("asks a signed-in person adding a provider too", () => {
    world.memberships = [personal()];
    renderUi(<SignUpForm type="provider" />);
    expect(caps()).not.toBeNull();
  });

  it("registers with what was chosen (delivering only)", async () => {
    world.signedIn = false;
    POST.mockResolvedValue({
      data: { sent: true, expires_in_seconds: 600, resend_after_seconds: 30 },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<SignUpForm type="provider" />);
    fireEvent.change(screen.getByPlaceholderText("NSDC Healthcare Academy"), { target: { value: "Centre Co" } });
    fireEvent.change(screen.getByRole("textbox", { name: /email/i }), { target: { value: "a@centre.example" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Sells courses/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Delivers training/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /privacy notice/ }));
    fireEvent.click(screen.getByRole("button", { name: /code/i }));
    await vi.waitFor(() => expect(POST).toHaveBeenCalled());
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/auth/org/register");
    expect(init.body).toMatchObject({
      tenant_type: "course_provider",
      sells_courses: false,
      delivers_training: true,
    });
  });

  it("sends the neutral pair for an employer, which delivers nothing", async () => {
    world.signedIn = false;
    POST.mockResolvedValue({
      data: { sent: true, expires_in_seconds: 600, resend_after_seconds: 30 },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<SignUpForm type="employer" />);
    fireEvent.change(screen.getByRole("textbox", { name: /email/i }), { target: { value: "h@hire.example" } });
    fireEvent.change(screen.getByPlaceholderText("Sunrise Multispeciality Hospital"), { target: { value: "Hire Co" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /privacy notice/ }));
    fireEvent.click(screen.getByRole("button", { name: /code/i }));
    await vi.waitFor(() => expect(POST).toHaveBeenCalled());
    const init = POST.mock.calls[0][1] as { body: Record<string, unknown> };
    expect(init.body).toMatchObject({ tenant_type: "employer", sells_courses: true, delivers_training: false });
  });

  it("holds the button while a provider has chosen neither", () => {
    world.signedIn = false;
    renderUi(<SignUpForm type="provider" />);
    fireEvent.click(screen.getByRole("checkbox", { name: /Sells courses/ }));
    expect(screen.getByRole("alert").textContent).toBe("Choose at least one.");
    expect(screen.getByRole("button", { name: /code/i })).toHaveProperty("disabled", true);
  });
});
