import { screen } from "@testing-library/react";
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
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<CandidateDashboard />);
    expect(await screen.findByText("3")).toBeTruthy();
    expect(screen.getByText("72")).toBeTruthy();
    expect(screen.getByText("65")).toBeTruthy();
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
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<CandidateDashboard />);
    await screen.findByText("10");
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
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
