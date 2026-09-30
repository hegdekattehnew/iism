import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProviderDashboard } from "@/components/employer/ProviderDashboard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const COURSE = { course_slug: "phlebotomy", course_title: "Phlebotomy Refresher", live: 3, total: 5 };

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("ProviderDashboard", () => {
  it("renders interest and enrolment conversion aggregated across every course", async () => {
    GET.mockResolvedValue({
      data: {
        published_courses: 4,
        interested_live: 6,
        interested_total: 9,
        enrolled: 2,
        conversion_rate: 0.22,
        courses: [COURSE],
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<ProviderDashboard orgSlug="learn-co" />);
    expect(await screen.findByText("4")).toBeTruthy();
    expect(screen.getByText("6")).toBeTruthy();
    expect(screen.getByText("9")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("22%")).toBeTruthy();
  });

  it("renders a bar per course and expands its interest detail on click", async () => {
    GET.mockResolvedValue({
      data: {
        published_courses: 1,
        interested_live: 6,
        interested_total: 9,
        enrolled: 2,
        conversion_rate: 0.22,
        courses: [COURSE],
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<ProviderDashboard orgSlug="learn-co" />);
    const bar = await screen.findByRole("button", { name: /Phlebotomy Refresher/ });
    expect(document.getElementById("ranked-bar-panel-phlebotomy")).toBeNull();
    fireEvent.click(bar);
    await vi.waitFor(() =>
      expect(document.getElementById("ranked-bar-panel-phlebotomy")).toBeTruthy(),
    );
  });

  it("renders nothing on a refusal, rather than a second error banner", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "Not Found" },
      response: { status: 404 },
    });
    const { container } = renderUi(<ProviderDashboard orgSlug="not-mine" />);
    await vi.waitFor(() => expect(GET).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });
});
