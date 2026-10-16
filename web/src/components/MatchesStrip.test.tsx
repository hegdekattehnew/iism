import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MatchesStrip } from "@/components/MatchesStrip";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a), POST: vi.fn() } }));

const DASHBOARD: Record<string, unknown> = {
  match_count: 14,
  best_score: 87,
  profile_completeness: 100,
  applied: 3,
  shortlisted: 1,
  hired: 0,
  top_matches: [],
  rating: null,
};

function serve(over: Record<string, unknown> = {}) {
  GET.mockImplementation(async () => ({
    data: { ...DASHBOARD, ...over },
    response: { status: 200 },
  }));
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

/** Sprint 70, UI-12: the numbers in one line, the charts one tap away. */
describe("the matches strip", () => {
  it("says it in one line, from the dashboard's own figures", async () => {
    serve();
    renderUi(<MatchesStrip />);
    expect(await screen.findByText("14 matches · best 87 · profile 100% complete")).toBeTruthy();
  });

  it("says 'one match' in the singular and leaves out a best score nobody has", async () => {
    serve({ match_count: 1, best_score: null, profile_completeness: 40 });
    renderUi(<MatchesStrip />);
    expect(await screen.findByText("1 match · profile 40% complete")).toBeTruthy();
  });

  it("says no matches, and does not claim a best", async () => {
    serve({ match_count: 0, best_score: null });
    renderUi(<MatchesStrip />);
    expect(await screen.findByText("No matches · profile 100% complete")).toBeTruthy();
  });

  it("does not draw the charts until asked, then draws them", async () => {
    serve();
    const { container } = renderUi(<MatchesStrip />);
    await screen.findByText(/14 matches/);
    expect(screen.queryByText("Your matches at a glance")).toBeNull();
    expect(screen.queryByText("Live matches")).toBeNull();

    const details = container.querySelector("details")!;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    await waitFor(() => expect(screen.getByText("Live matches")).toBeTruthy());
  });

  it("is a placeholder while loading, never a zero", () => {
    GET.mockReturnValue(new Promise(() => undefined));
    renderUi(<MatchesStrip />);
    expect(screen.queryByText(/0 matches|No matches/)).toBeNull();
  });

  it("says nothing when the dashboard cannot load (the list below says why)", async () => {
    GET.mockImplementation(async () => ({
      data: undefined,
      error: { detail: "x" },
      response: { status: 500 },
    }));
    const { container } = renderUi(<MatchesStrip />);
    await waitFor(() => expect(GET).toHaveBeenCalled());
    await waitFor(() => expect(container.textContent).toBe(""));
  });
});
