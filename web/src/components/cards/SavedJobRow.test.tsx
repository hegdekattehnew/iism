import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SavedJobRow } from "@/components/cards/SavedJobRow";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

beforeEach(resetWorld);

/** Sprint 87, BL-19.17: a saved vacancy is one link, not a card with a link in it. */
describe("SavedJobRow", () => {
  it("is one link to the vacancy that holds the mark, the title, the employer and a chevron", () => {
    const { container } = renderUi(<SavedJobRow slug="ward-attendant" title="Ward Attendant" employer="Apollo Care" />);
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("/jobs/ward-attendant");
    expect(link.textContent).toContain("Ward Attendant");
    expect(link.textContent).toContain("Apollo Care");
    expect(container.querySelectorAll("a").length).toBe(1);
    expect(link.querySelector("svg")).toBeTruthy();
  });

  it("has the employer's mark, hidden from a screen reader, and the name beside it", () => {
    renderUi(<SavedJobRow slug="x" title="X" employer="Apollo Care" />);
    const mark = screen.getByRole("link").querySelector("[aria-hidden='true']") as HTMLElement;
    expect(mark.textContent).toBe("A");
    expect(screen.getByText("Apollo Care")).toBeTruthy();
  });

  it("holds no button, so the whole card can be the target", () => {
    renderUi(<SavedJobRow slug="x" title="X" employer="Y" />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByRole("link").className).toContain("min-h-11");
  });
});
