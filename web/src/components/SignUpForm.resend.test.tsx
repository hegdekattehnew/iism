import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SignUpForm } from "@/components/SignUpForm";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: vi.fn(), POST: (...a: unknown[]) => POST(...a), PUT: vi.fn(), DELETE: vi.fn() },
}));

/**
 * Sprint 56, BL-14.1. A one-time code is the only way in, so a code that never arrives is a lost
 * user, and this form had no way to ask again. These pin what the person sees and what each press
 * actually asks the server: especially that an *organisation* asks for a sign-in code and never
 * registers a second time (the address exists now, so a second registration would hold a second
 * pending organisation of the same name and fail the person at verification).
 */
const sent = (resendAfter = 30) => ({
  data: { sent: true, expires_in_seconds: 300, resend_after_seconds: resendAfter, debug_code: null },
  error: undefined,
  response: { status: 200, headers: new Headers() },
});
const tooSoon = (seconds: number) => ({
  data: undefined,
  error: { detail: "wait" },
  response: { status: 429, headers: new Headers({ "retry-after": String(seconds) }) },
});

beforeEach(() => {
  resetWorld();
  POST.mockReset();
  world.signedIn = false;
  vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
});
afterEach(() => vi.useRealTimers());

async function signUp(type: "seeker" | "employer") {
  renderUi(<SignUpForm type={type} />);
  if (type === "seeker") {
    fireEvent.change(screen.getByPlaceholderText("98765 43210"), { target: { value: "9876543210" } });
  } else {
    fireEvent.change(screen.getByPlaceholderText("Sunrise Multispeciality Hospital"), {
      target: { value: "Acme Care" },
    });
    fireEvent.change(screen.getByLabelText(/Work email/), { target: { value: "hr@acme.example" } });
  }
  fireEvent.click(screen.getByRole("checkbox", { name: /privacy notice/ }));
  fireEvent.click(screen.getByRole("button", { name: "Send the code" }));
  await screen.findByRole("button", { name: /Send a new code in 30s/ });
}

const pathsAsked = () => POST.mock.calls.map((c) => String(c[0]));

describe("SignUpForm: asking for a new code", () => {
  it("shows a countdown, then lets a job seeker ask again for the same number", async () => {
    POST.mockResolvedValue(sent());
    await signUp("seeker");

    const button = screen.getByRole("button", { name: /Send a new code in 30s/ });
    expect(button).toHaveProperty("disabled", true);

    await act(() => vi.advanceTimersByTimeAsync(31_000));
    const ready = await screen.findByRole("button", { name: "Send a new code" });
    expect(ready).toHaveProperty("disabled", false);

    fireEvent.click(ready);
    await screen.findByRole("button", { name: /Send a new code in 30s/ });
    expect(pathsAsked()).toEqual(["/auth/otp/request", "/auth/otp/request"]);
    expect(POST.mock.calls[1][1].body).toEqual({ phone: "9876543210" });
  });

  it("asks an organisation for a sign-in code, never to register again", async () => {
    POST.mockResolvedValue(sent());
    await signUp("employer");
    await act(() => vi.advanceTimersByTimeAsync(31_000));

    fireEvent.click(await screen.findByRole("button", { name: "Send a new code" }));
    await screen.findByRole("button", { name: /Send a new code in 30s/ });

    expect(pathsAsked()).toEqual(["/auth/org/register", "/auth/email/otp/request"]);
    expect(POST.mock.calls[1][1].body).toEqual({ email: "hr@acme.example" });
  });

  it("counts down from the wait the server names when asked too soon", async () => {
    POST.mockResolvedValueOnce(sent(1)).mockResolvedValueOnce(tooSoon(12));
    renderUi(<SignUpForm type="seeker" />);
    fireEvent.change(screen.getByPlaceholderText("98765 43210"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /privacy notice/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send the code" }));
    await screen.findByRole("button", { name: /Send a new code in 1s/ });
    await act(() => vi.advanceTimersByTimeAsync(2_000));

    fireEvent.click(await screen.findByRole("button", { name: "Send a new code" }));
    expect(await screen.findByText(/wait 12 seconds/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Send a new code in 12s/ })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("does not run slow when the tab was in the background: it counts a deadline, not ticks", async () => {
    POST.mockResolvedValue(sent());
    await signUp("seeker");
    // The clock moved on by a minute while no timer fired.
    vi.setSystemTime(Date.now() + 60_000);
    await act(() => vi.advanceTimersByTimeAsync(600));
    expect(await screen.findByRole("button", { name: "Send a new code" })).toBeTruthy();
  });
});
