import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignUpForm } from "@/components/SignUpForm";
import { renderUi, resetWorld, world } from "@/test/harness";

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
  world.signedIn = false;
});

/** Sprint 86, BL-19.16: the consent row and the code step's buttons are 44 px. */
describe("SignUpForm: targets", () => {
  it("makes the whole consent row the target, and the box a 20 px one", () => {
    renderUi(<SignUpForm type="seeker" />);
    const box = screen.getByRole("checkbox");
    const row = box.closest("label") as HTMLElement;
    expect(row.className).toContain("min-h-11");
    expect(box.className).toContain("h-5 w-5");
    // the links stay inside the sentence the person agrees to
    expect(row.querySelector("a[href='/privacy']")).toBeTruthy();
    expect(row.querySelector("a[href='/terms']")).toBeTruthy();
  });

  it("makes the code step's two buttons 44 px", async () => {
    POST.mockResolvedValue({
      data: { sent: true, expires_in_seconds: 300, resend_after_seconds: 30, debug_code: null },
      error: undefined,
      response: { status: 200, headers: new Headers() },
    });
    renderUi(<SignUpForm type="seeker" />);
    fireEvent.change(screen.getByPlaceholderText("98765 43210"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Send the code" }));
    const change = await screen.findByRole("button", { name: "Change these details" });
    expect(change.className).toContain("min-h-11");
    expect(screen.getByRole("button", { name: /Send a new code/ }).className).toContain("min-h-11");
  });
});
