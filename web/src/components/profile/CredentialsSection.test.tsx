import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CredentialsSection } from "@/components/profile/CredentialsSection";
import { authMock, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const POST = vi.fn();
const DELETE = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: vi.fn(),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: (...a: unknown[]) => DELETE(...a),
  },
}));

/**
 * Sprint 56, BL-14.2. A one-time code is the only way in, so the phone number or email it goes to
 * is the account. The screen used to add the credential that was missing and do nothing else.
 */
const code = (resendAfter = 30) => ({
  data: { sent: true, expires_in_seconds: 300, resend_after_seconds: resendAfter, debug_code: null },
  error: undefined,
  response: { status: 200, headers: new Headers() },
});
const changed = {
  data: {
    access_token: "new-access",
    refresh_token: "new-refresh",
    token_type: "bearer",
    expires_in: 900,
    user: {},
  },
  error: undefined,
  response: { status: 200, headers: new Headers() },
};
const refused = (status: number) => ({
  data: undefined,
  error: { detail: "no" },
  response: { status, headers: new Headers() },
});

beforeEach(() => {
  resetWorld();
  POST.mockReset();
  DELETE.mockReset();
  vi.mocked(authMock.setTokens).mockClear();
  vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
});
afterEach(() => vi.useRealTimers());

const bothVerified = () => {
  world.account = {
    phone: "+919812349999",
    email: "owner@clinic.example",
    phone_verified_at: "2026-01-01T00:00:00Z",
    email_verified_at: "2026-01-02T00:00:00Z",
  };
};

describe("CredentialsSection: what is offered", () => {
  it("asks a phone-only person to add an email, and offers no removal", () => {
    renderUi(<CredentialsSection />);
    expect(screen.getByText(/Add an email address too/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add" })).toBeTruthy(); // the email
    expect(screen.getByRole("button", { name: "Change" })).toBeTruthy(); // the phone
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
    expect(screen.getByText(/only verified way in/)).toBeTruthy();
  });

  it("offers change and remove for both when both are verified", () => {
    bothVerified();
    renderUi(<CredentialsSection />);
    expect(screen.getAllByRole("button", { name: "Change" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(2);
    expect(screen.queryByText(/Add an email address too/)).toBeNull();
  });

  it("does not offer to remove a credential when the other one is not verified", () => {
    bothVerified();
    world.account.email_verified_at = null; // typed in, never proven
    renderUi(<CredentialsSection />);
    // Removing the phone would leave only an address nobody has proved: the phone's Remove is
    // withheld; the unverified email can go, because the verified phone remains.
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(1);
  });

  it("shows a placeholder, not a blank, while the account is still loading", () => {
    world.pending = true;
    const { container } = renderUi(<CredentialsSection />);
    expect(container.querySelectorAll("[data-loading]").length).toBeGreaterThan(0);
  });
});

describe("CredentialsSection: changing a number", () => {
  const changePhone = async () => {
    bothVerified();
    POST.mockResolvedValueOnce(code());
    renderUi(<CredentialsSection />);
    fireEvent.click(screen.getAllByRole("button", { name: "Change" })[0]);
    fireEvent.change(screen.getByLabelText(/Phone number/), { target: { value: "9000000001" } });
    fireEvent.click(screen.getByRole("button", { name: "Send the code" }));
    await screen.findByText(/We sent a six-digit code to 9000000001/);
    fireEvent.change(screen.getByLabelText(/Six-digit code/), { target: { value: "123456" } });
  };

  it("sends the code to the new number, then replaces, and keeps the person signed in", async () => {
    await changePhone();
    POST.mockResolvedValueOnce(changed);
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() =>
      expect(authMock.setTokens).toHaveBeenCalledWith(
        expect.objectContaining({ access_token: "new-access", refresh_token: "new-refresh" }),
      ),
    );
    expect(POST.mock.calls.map((c) => c[0])).toEqual([
      "/me/credentials/phone",
      "/me/credentials/phone/replace",
    ]);
    expect(POST.mock.calls[1][1].body).toEqual({ phone: "9000000001", code: "123456" });
  });

  it("names a number that belongs to someone else, and stores no tokens", async () => {
    await changePhone();
    POST.mockResolvedValueOnce(refused(409));
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText(/already belongs to another account/)).toBeTruthy();
    expect(authMock.setTokens).not.toHaveBeenCalled();
  });

  it("counts down before another code can be asked for", async () => {
    await changePhone();
    const resend = screen.getByRole("button", { name: /Send a new code in 30s/ });
    expect(resend).toHaveProperty("disabled", true);
    await act(() => vi.advanceTimersByTimeAsync(31_000));
    expect(await screen.findByRole("button", { name: "Send a new code" })).toHaveProperty(
      "disabled",
      false,
    );
  });
});

describe("CredentialsSection: adding and removing", () => {
  it("adds an email with the verify endpoint, which signs nobody out", async () => {
    POST.mockResolvedValueOnce(code()).mockResolvedValueOnce({
      data: { id: "u" },
      error: undefined,
      response: { status: 200, headers: new Headers() },
    });
    renderUi(<CredentialsSection />);
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    fireEvent.change(screen.getByLabelText(/Email address/), {
      target: { value: "me@example.org" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send the code" }));
    await screen.findByText(/We sent a six-digit code to me@example.org/);
    fireEvent.change(screen.getByLabelText(/Six-digit code/), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify and add" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(2));
    expect(POST.mock.calls[1][0]).toBe("/me/credentials/email/verify");
    expect(authMock.setTokens).not.toHaveBeenCalled();
  });

  it("asks twice before removing, then stores the new tokens", async () => {
    bothVerified();
    DELETE.mockResolvedValueOnce(changed);
    renderUi(<CredentialsSection />);
    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[1]); // the email
    expect(screen.getByText(/Remove your email address\?/)).toBeTruthy();
    expect(DELETE).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Yes, remove it" }));
    await waitFor(() => expect(authMock.setTokens).toHaveBeenCalled());
    expect(DELETE.mock.calls[0][0]).toBe("/me/credentials/email");
  });

  it("explains a refused removal without storing anything", async () => {
    bothVerified();
    DELETE.mockResolvedValueOnce(refused(409));
    renderUi(<CredentialsSection />);
    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Yes, remove it" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(authMock.setTokens).not.toHaveBeenCalled();
  });
});
