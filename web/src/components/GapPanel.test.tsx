import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GapPanel } from "@/components/GapPanel";
import { setCourseBudget } from "@/lib/course-budget";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

const GAP = {
  application_id: "a1",
  score: 40,
  coverage: 0.4,
  missing_mandatory: 1,
  capped_by_mandatory: true,
  missing: [
    {
      skill_id: "s1",
      nos_code: "HSS/N1",
      name: "Dress wounds",
      importance: 3,
      is_mandatory: true,
    },
  ],
  courses: [
    {
      slug: "wound-care",
      title: "Wound care",
      mode: "offline",
      language: "both",
      fee_inr: 4000,
      closes: ["Dress wounds"],
      closes_count: 1,
      gap_size: 1,
      covers_mandatory: 1,
      location_state: "Maharashtra",
      location_district: "Pune",
      starts_on: null,
      seats_left: null,
      reach: "state",
      started: false,
      full: false,
      within_budget: true,
      attendable: true,
    },
  ],
};

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  window.localStorage.clear();
  act(() => setCourseBudget(null));
  GET.mockResolvedValue({
    data: GAP,
    error: undefined,
    response: { status: 200 },
  });
});

describe("why not me: the courses that close the gap, as a person can take them", () => {
  it("asks without a budget until the person gives one", async () => {
    renderUi(<GapPanel applicationId="a1" />);
    expect(await screen.findByText("Wound care")).toBeTruthy();
    expect(GET.mock.calls[0][1].params.query).toEqual({});
  });

  it("sends the budget the person gave, and shows where and when for each course", async () => {
    act(() => setCourseBudget(5000));
    renderUi(<GapPanel applicationId="a1" />);
    expect(await screen.findByText("Wound care")).toBeTruthy();
    await waitFor(() => expect(GET).toHaveBeenCalled());
    expect(GET.mock.calls[0][1].params.query).toEqual({ budget_inr: 5000 });
    expect(screen.getByText(/Pune, Maharashtra/)).toBeTruthy();
    expect(screen.getByText("In your state")).toBeTruthy();
  });
});
