import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CandidateDashboard } from "@/components/CandidateDashboard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const TOP_MATCH = {
  job_slug: "cashier-nagpur",
  job_title: "Cashier",
  score: 78,
  coverage: 0.8,
  missing_mandatory: 0,
  capped_by_mandatory: false,
  nsqf_level_min: 4,
  level_shortfall: null,
};

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("CandidateDashboard", () => {
  it("renders every number the endpoint returns", async () => {
    GET.mockResolvedValue({
      data: {
        match_count: 3,
        best_score: 72,
        applied: 2,
        shortlisted: 1,
        hired: 0,
        profile_completeness: 65,
        top_matches: [TOP_MATCH],
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<CandidateDashboard />);
    expect(await screen.findByText("3")).toBeTruthy();
    expect(screen.getByText("72")).toBeTruthy();
    expect(screen.getByText("65%")).toBeTruthy();
    // The one way into the career ladder (the header has no room for it).
    expect(
      screen.getByRole("link", { name: "See where you could move next" }).getAttribute("href"),
    ).toBe("/career-paths");
  });

  it("shows the employers' rating, and shows nothing at all when there is none", async () => {
    const base = {
      match_count: 1,
      best_score: 50,
      applied: 0,
      shortlisted: 0,
      hired: 0,
      profile_completeness: 40,
      top_matches: [],
    };
    GET.mockResolvedValue({
      data: { ...base, rating: { average: 4.5, count: 6 } },
      error: undefined,
      response: { status: 200 },
    });
    const first = renderUi(<CandidateDashboard />);
    expect(await screen.findByText("Employers rate you")).toBeTruthy();
    expect(screen.getByText("4.5")).toBeTruthy();
    expect(screen.getByText("6 ratings")).toBeTruthy();
    first.unmount();

    // "No ratings yet" is not "rated 0": no tile, not a zero.
    GET.mockResolvedValue({ data: { ...base, rating: null }, error: undefined, response: { status: 200 } });
    renderUi(<CandidateDashboard />);
    await screen.findByText("40%");
    expect(screen.queryByText("Employers rate you")).toBeNull();
  });

  it("renders a dash for best_score rather than a false zero when there are no matches yet", async () => {
    GET.mockResolvedValue({
      data: {
        match_count: 0,
        best_score: null,
        applied: 0,
        shortlisted: 0,
        hired: 0,
        profile_completeness: 10,
        top_matches: [],
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<CandidateDashboard />);
    await screen.findByText("10%");
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("expands a top match into its coverage detail on click", async () => {
    GET.mockResolvedValue({
      data: {
        match_count: 1,
        best_score: 78,
        applied: 0,
        shortlisted: 0,
        hired: 0,
        profile_completeness: 50,
        top_matches: [TOP_MATCH],
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<CandidateDashboard />);
    const bar = await screen.findByRole("button", { name: /Cashier/ });
    expect(document.getElementById("ranked-bar-panel-cashier-nagpur")).toBeNull();
    fireEvent.click(bar);
    await vi.waitFor(() =>
      expect(document.getElementById("ranked-bar-panel-cashier-nagpur")).toBeTruthy(),
    );
  });

  it("renders nothing rather than a second error banner when the caller is refused", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "Not Found" },
      response: { status: 404 },
    });
    const { container } = renderUi(<CandidateDashboard />);
    await vi.waitFor(() => expect(GET).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });
});
