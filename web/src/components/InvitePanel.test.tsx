import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InvitePanel } from "@/components/InvitePanel";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

/**
 * The only screen in the product somebody sees before they have an account,
 * and the front of the sprint's riskiest seam.
 */

const panel = () => <InvitePanel token="tok-123" />;

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  GET.mockResolvedValue({
    data: {
      organisation: "Apollo Care Hospitals",
      organisation_slug: "apollo-care",
      tenant_type: "employer",
      role: "member",
    },
    error: undefined,
    response: { status: 200 },
  });
});

describe("InvitePanel — signed in", () => {
  beforeEach(() => {
    world.signedIn = true;
    POST.mockResolvedValue({
      data: { organisation_slug: "apollo-care", role: "member" },
      error: undefined,
      response: { status: 200 },
    });
  });

  it("names the organisation and accepts onto the existing account", async () => {
    renderUi(panel());
    expect(await screen.findByText(/Apollo Care Hospitals/)).toBeTruthy();
    expect(screen.getByText(/Accepting adds this organisation to your account/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Accept and join" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect((POST.mock.calls[0] as [string])[0]).toBe("/invitations/{token}/accept");
  });

  it("never offers to create a second account", async () => {
    // One identity, many roles (ADR-038). A signed-in person accepting must
    // not be walked through a signup.
    renderUi(panel());
    await screen.findByText(/Apollo Care Hospitals/);
    expect(screen.queryByRole("button", { name: "Send me a code" })).toBeNull();
  });
});

describe("InvitePanel — no account yet", () => {
  beforeEach(() => {
    world.signedIn = false;
  });

  it("sends a code without ever asking for an address", async () => {
    // The address comes off the invitation, server side. A field here would
    // let a forwarded link mint an account at an address of the holder's
    // choosing.
    POST.mockResolvedValue({
      data: { sent: true, expires_in_seconds: 300, email_hint: "ne***@apollo-care.example" },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(panel());
    await screen.findByText(/Apollo Care Hospitals/);
    expect(screen.queryByPlaceholderText(/@/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Send me a code" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect((POST.mock.calls[0] as [string])[0]).toBe("/invitations/{token}/claim");
    expect(await screen.findByText(/ne\*\*\*@apollo-care.example/)).toBeTruthy();
  });

  it("sends consent with the verification, or the new account 428s forever", async () => {
    POST.mockResolvedValueOnce({
      data: { sent: true, expires_in_seconds: 300, email_hint: "ne***@apollo-care.example" },
      error: undefined,
      response: { status: 200 },
    }).mockResolvedValueOnce({
      data: {
        access_token: "a",
        refresh_token: "r",
        expires_in: 900,
        created: true,
        organisation_slug: "apollo-care",
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(panel());
    await screen.findByText(/Apollo Care Hospitals/);
    fireEvent.click(screen.getByRole("button", { name: "Send me a code" }));

    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Create my account and join" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(2));
    const [path, init] = POST.mock.calls[1] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/invitations/{token}/verify");
    expect(init.body).toEqual({ code: "123456", consent_version: "2026-09-11" });
    expect(init.body).not.toHaveProperty("email");
  });
});

describe("InvitePanel — a spent invitation", () => {
  it("says it is finished rather than that it never existed", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "x" },
      response: { status: 410 },
    });
    renderUi(panel());
    expect(await screen.findByText("This invitation is no longer open")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Accept and join" })).toBeNull();
  });

  it("distinguishes a link that was never real", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "x" },
      response: { status: 404 },
    });
    renderUi(panel());
    expect(await screen.findByText("We could not find that invitation")).toBeTruthy();
  });
});
