import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignInForm } from "@/components/SignInForm";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: vi.fn(), POST: (...a: unknown[]) => POST(...a), PUT: vi.fn(), DELETE: vi.fn() },
}));

beforeEach(() => {
  resetWorld();
  POST.mockReset();
});

const ok = (data: object) => ({ data, error: undefined, response: { status: 200, headers: new Headers() } });

/** Sprint 86, BL-19.16: sign-in's two fields are the library's, and its controls are 44 px. */
describe("SignInForm: the identifier field", () => {
  it("is labelled, and says beside itself what is wrong when it is left empty", async () => {
    renderUi(<SignInForm />);
    const box = screen.getByLabelText("Mobile number or email");
    fireEvent.focus(box);
    fireEvent.blur(box);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Fill in this field.");
    expect(box.getAttribute("aria-invalid")).toBe("true");
    expect(box.getAttribute("aria-describedby")).toBe(alert.id);
  });

  it("says nothing while the person has not been to the field, and nothing once it is filled", async () => {
    renderUi(<SignInForm />);
    expect(screen.queryByRole("alert")).toBeNull();
    const box = screen.getByLabelText("Mobile number or email");
    fireEvent.change(box, { target: { value: "9876543210" } });
    fireEvent.blur(box);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(box.getAttribute("aria-invalid")).toBeNull();
  });

  it("is 44 px tall and keeps its larger type", () => {
    renderUi(<SignInForm />);
    const cls = screen.getByLabelText("Mobile number or email").className;
    expect(cls).toContain("min-h-11");
    expect(cls).toContain("text-base");
  });
});

describe("SignInForm: the code step", () => {
  async function toCodeStep() {
    POST.mockResolvedValue(ok({ sent: true, expires_in_seconds: 300, resend_after_seconds: 30, debug_code: null }));
    renderUi(<SignInForm />);
    fireEvent.change(screen.getByLabelText("Mobile number or email"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: "Send code" }));
    return screen.findByLabelText("6-digit code");
  }

  it("has the code in a labelled field that keeps digits only and is 44 px", async () => {
    const box = await toCodeStep();
    fireEvent.change(box, { target: { value: "12ab34" } });
    expect((box as HTMLInputElement).value).toBe("1234");
    expect(box.className).toContain("min-h-11");
    expect(box.className).toContain("text-2xl");
    expect(box.getAttribute("maxlength")).toBe("6");
  });

  it("makes the two ways back 44 px", async () => {
    await toCodeStep();
    expect(screen.getByRole("button", { name: "Use a different one" }).className).toContain("min-h-11");
    expect(screen.getByRole("button", { name: /Send a new code/ }).className).toContain("min-h-11");
  });

  it("makes the link to sign up, shown for a number with no account, 44 px", async () => {
    const box = await toCodeStep();
    POST.mockResolvedValue({ data: undefined, error: {}, response: { status: 428, headers: new Headers() } });
    fireEvent.change(box, { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify and continue" }));
    const link = await screen.findByRole("link", { name: "Create an account" });
    await waitFor(() => expect(link.className).toContain("min-h-11"));
    expect(link.getAttribute("href")).toBe("/signup/seeker");
  });
});
