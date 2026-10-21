import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OperatorDashboard } from "@/components/ops/OperatorDashboard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("OperatorDashboard", () => {
  it("renders the queue counts and platform totals together", async () => {
    GET.mockResolvedValue({
      data: {
        unverified_organisations: 3,
        unverified_certifications: 5,
        organisations: 40,
        candidates: 400,
        published_jobs: 20,
        published_courses: 50,
        scarce_skills: [],
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<OperatorDashboard />);
    expect(await screen.findByText("3")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText("40")).toBeTruthy();
    expect(screen.getByText("400")).toBeTruthy();
  });

  it("renders a ranked bar per scarce skill", async () => {
    GET.mockResolvedValue({
      data: {
        unverified_organisations: 0,
        unverified_certifications: 0,
        organisations: 1,
        candidates: 1,
        published_jobs: 1,
        published_courses: 1,
        scarce_skills: [
          { nos_code: "OPS/N9001", name: "Rare Standard", required_by: 8, held_by: 0 },
        ],
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<OperatorDashboard />);
    expect(await screen.findByText("Rare Standard")).toBeTruthy();
    expect(screen.getByText("8")).toBeTruthy();
  });

  it("shows the failure message rather than nothing, since operators have no other screen to fall back on", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "server error" },
      response: { status: 500 },
    });
    renderUi(<OperatorDashboard />);
    expect(await screen.findByText("The dashboard could not be loaded.")).toBeTruthy();
  });

  it("keeps its heading and its tiles, with dashes and never zeros, while the answer is on its way", () => {
    GET.mockImplementation(() => new Promise(() => undefined));
    const { container } = renderUi(<OperatorDashboard />);
    expect(screen.getByText("Overview")).toBeTruthy();
    expect(screen.getAllByText("—").length).toBe(6);
    expect(screen.queryByText("0")).toBeNull();
    // The scarce-skills row is reserved, so what lands later does not move the queue below it.
    expect(container.querySelector("details")).toBeNull();
    expect(container.querySelector("[class*='h-11']")).toBeTruthy();
  });

  it("puts the scarce skills behind one row of fixed height, closed, present even when there are none", async () => {
    GET.mockResolvedValue({
      data: {
        unverified_organisations: 0,
        unverified_certifications: 0,
        organisations: 1,
        candidates: 1,
        published_jobs: 1,
        published_courses: 1,
        scarce_skills: [],
      },
      error: undefined,
      response: { status: 200 },
    });
    const { container } = renderUi(<OperatorDashboard />);
    await screen.findByText("Scarcest standards, market-wide");
    const row = container.querySelector("details")!;
    expect(row.hasAttribute("open")).toBe(false);
    expect(row.querySelector("summary")!.className).toMatch(/min-h-11/);
  });
});

/** Sprint 89, BL-19.19: the overview's figures are tiles with a mark each, and the same shape while they load. */
describe("OperatorDashboard -- the tiles", () => {
  const FULL = {
    unverified_organisations: 3,
    unverified_certifications: 5,
    organisations: 40,
    candidates: 400,
    published_jobs: 20,
    published_courses: 50,
    scarce_skills: [],
  };

  it("draws six tiles with six different marks", async () => {
    GET.mockResolvedValue({ data: FULL, error: undefined, response: { status: 200 } });
    const { container } = renderUi(<OperatorDashboard />);
    await screen.findByText("400");
    const tiles = [...container.querySelectorAll(".grid > div")] as HTMLElement[];
    expect(tiles.length).toBe(6);
    const shapes = tiles.map((t) => t.querySelector("[aria-hidden='true'] svg")!.innerHTML);
    expect(new Set(shapes).size).toBe(6);
    expect(tiles[0].textContent).toContain("Awaiting verification");
  });

  it("is the same six tiles, with a dash each, before the figures arrive (so nothing moves when they do)", async () => {
    GET.mockImplementation(() => new Promise(() => undefined));
    const { container } = renderUi(<OperatorDashboard />);
    const tiles = [...container.querySelectorAll(".grid > div")] as HTMLElement[];
    expect(tiles.length).toBe(6);
    for (const t of tiles) {
      expect(t.textContent).toContain("—");
      expect(t.querySelector("[aria-hidden='true'] svg")).toBeTruthy();
    }
    expect(screen.queryByText("0")).toBeNull();
  });

  it("shows a true zero as 0 and not a dash", async () => {
    GET.mockResolvedValue({ data: { ...FULL, unverified_organisations: 0 }, error: undefined, response: { status: 200 } });
    const { container } = renderUi(<OperatorDashboard />);
    await screen.findByText("400");
    expect((container.querySelectorAll(".grid > div")[0] as HTMLElement).textContent).toContain("0");
    expect((container.querySelectorAll(".grid > div")[0] as HTMLElement).textContent).not.toContain("—");
  });
});
