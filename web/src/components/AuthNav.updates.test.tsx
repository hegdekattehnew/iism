import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthNav } from "@/components/AuthNav";
import { personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

let unread = 0;
const asked = vi.fn();
vi.mock("@/lib/unread-count", () => ({
  useUnreadCount: (signedIn: boolean) => {
    asked(signedIn);
    return signedIn ? unread : 0;
  },
}));

beforeEach(() => {
  resetWorld();
  asked.mockReset();
  unread = 0;
  world.memberships = [personal()];
});

describe("the header's Updates link (Sprint 60, BL-14.9)", () => {
  it("links to the page and shows how many are unread, in words for a screen reader", () => {
    unread = 3;
    renderUi(<AuthNav />);
    const link = screen.getByRole("link", { name: "Updates 3 unread" });
    expect(link.getAttribute("href")).toBe("/notifications");
    expect(link.textContent).toContain("3");
    // The drawn number is hidden from assistive technology; the words carry it.
    expect(link.querySelector('[aria-hidden="true"]')?.textContent).toBe("3");
    expect(link.getAttribute("aria-label")).toBeNull();
  });

  it("shows no count when there is nothing unread", () => {
    renderUi(<AuthNav />);
    const link = screen.getByRole("link", { name: "Updates" });
    expect(link.textContent).toBe("Updates");
  });

  it("caps a large count", () => {
    unread = 250;
    renderUi(<AuthNav />);
    expect(screen.getByRole("link", { name: /Updates/ }).textContent).toContain(
      "99+",
    );
  });

  it("is not there for somebody signed out, and the count is not asked for", () => {
    world.signedIn = false;
    renderUi(<AuthNav />);
    expect(screen.queryByRole("link", { name: /Updates/ })).toBeNull();
    expect(asked).toHaveBeenCalledWith(false);
  });

  it("is in the stacked mobile list too", () => {
    unread = 1;
    renderUi(<AuthNav stacked />);
    expect(screen.getByRole("link", { name: "Updates 1 unread" })).toBeTruthy();
  });
});
