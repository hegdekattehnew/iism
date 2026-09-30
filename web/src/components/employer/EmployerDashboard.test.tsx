import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EmployerDashboard } from "@/components/employer/EmployerDashboard";
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

describe("EmployerDashboard", () => {
  it("renders vacancies and applicants aggregated across every posting", async () => {
    GET.mockResolvedValue({
      data: { posted_jobs: 5, open_jobs: 4, applied: 12, shortlisted: 3, hired: 1 },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<EmployerDashboard orgSlug="apollo-care-hospitals" />);
    expect(await screen.findByText("5")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
  });

  it("renders nothing on a refusal, rather than a second error banner", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "Not Found" },
      response: { status: 404 },
    });
    const { container } = renderUi(<EmployerDashboard orgSlug="not-mine" />);
    await vi.waitFor(() => expect(GET).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });
});
