import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FrameworkBand } from "@/components/FrameworkBand";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

/**
 * The framework figures, moved from the homepage to About (Sprint 70, UI-01/02). The rules did not
 * move: a figure says what it counts, digits are grouped the Indian way, and while the answer is
 * unknown a tile is a skeleton, never a zero (a zero here would be a lie about the corpus).
 */

const STATS = {
  standards: 21303,
  qualifications: 4424,
  criteria: 238370,
  awarding_bodies: 106,
  sectors: 43,
  entry_routes: 14405,
};

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("FrameworkBand", () => {
  it("shows the six framework figures, grouped the Indian way", async () => {
    GET.mockImplementation(async () => ({ data: STATS }));
    const { container } = renderUi(<FrameworkBand />);
    expect(await screen.findByText("2,38,370")).toBeTruthy();
    const term = (label: string) => screen.getByText(label).parentElement as HTMLElement;
    expect(within(term("National Occupational Standards")).getByText("21,303")).toBeTruthy();
    expect(within(term("Qualification Packs")).getByText("4,424")).toBeTruthy();
    expect(within(term("Awarding bodies")).getByText("106")).toBeTruthy();
    expect(within(term("Sectors")).getByText("43")).toBeTruthy();
    const grid = container.querySelector("dl")!;
    expect(grid.children).toHaveLength(6);
    expect(grid.className).toContain("sm:grid-cols-3");
  });

  it("says what it is and where the figures come from", async () => {
    GET.mockImplementation(async () => ({ data: STATS }));
    renderUi(<FrameworkBand />);
    expect(await screen.findByText("Built on the national framework, not a guess")).toBeTruthy();
    expect(screen.getByText(/Counted live from the platform database/)).toBeTruthy();
  });

  it("renders skeletons, never zeros, while loading or when the API is unreachable", async () => {
    GET.mockImplementation(async () => ({ data: undefined, error: { detail: "down" } }));
    renderUi(<FrameworkBand />);
    await waitFor(() => expect(GET).toHaveBeenCalled());
    expect(screen.queryByText("0")).toBeNull();
    expect(screen.queryByText("21,303")).toBeNull();
  });

  it("holds a definition list of terms and definitions only", async () => {
    GET.mockImplementation(async () => ({ data: STATS }));
    const { container } = renderUi(<FrameworkBand />);
    await screen.findByText("2,38,370");
    for (const group of container.querySelector("dl")!.children) {
      for (const child of group.children) expect(["DT", "DD"]).toContain(child.tagName);
    }
  });
});
