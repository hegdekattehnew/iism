import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SignInForm } from "@/components/SignInForm";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: vi.fn(), POST: (...a: unknown[]) => POST(...a), PUT: vi.fn(), DELETE: vi.fn() },
}));

/** Sprint 56, BL-14.1: the resend control on sign-in counts down instead of inviting a press the
 * server will refuse, and a refusal names how long to wait. */
const sent = (resendAfter = 30) => ({
  data: { sent: true, expires_in_seconds: 300, resend_after_seconds: resendAfter, debug_code: null },
  error: undefined,
  response: { status: 200, headers: new Headers() },
});

beforeEach(() => {
  resetWorld();
  POST.mockReset();
  vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
});
afterEach(() => vi.useRealTimers());

const askFor = async (value: string) => {
  renderUi(<SignInForm />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: /Send/ }));
};

describe("SignInForm: asking for a new code", () => {
  it("counts down, then asks the same endpoint again", async () => {
    POST.mockResolvedValue(sent());
    await askFor("9876543210");
    const waiting = await screen.findByRole("button", { name: /Send a new code in 30s/ });
    expect(waiting).toHaveProperty("disabled", true);

    await act(() => vi.advanceTimersByTimeAsync(31_000));
    fireEvent.click(await screen.findByRole("button", { name: "Send a new code" }));
    await screen.findByRole("button", { name: /Send a new code in 30s/ });
    expect(POST.mock.calls.map((c) => c[0])).toEqual(["/auth/otp/request", "/auth/otp/request"]);
  });

  it("asks an email address through the email endpoint", async () => {
    POST.mockResolvedValue(sent());
    await askFor("owner@clinic.example");
    await screen.findByRole("button", { name: /Send a new code in 30s/ });
    expect(POST.mock.calls[0][0]).toBe("/auth/email/otp/request");
  });

  it("says how long to wait when the server refuses a request that came too soon", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "wait" },
      response: { status: 429, headers: new Headers({ "retry-after": "20" }) },
    });
    await askFor("9876543210");
    expect(await screen.findByText(/wait 20 seconds/)).toBeTruthy();
  });
});
