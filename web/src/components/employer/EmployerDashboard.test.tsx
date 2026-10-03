import { fireEvent, screen } from "@testing-library/react";
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

const JOB = {
  job: { slug: "cashier-nagpur", title: "Cashier", employment_type: "full_time" },
  pool: 6,
  ready: 4,
  nearly: 1,
  applications: 3,
  new_applications: 2,
};

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("EmployerDashboard", () => {
  it("renders vacancies and applicants aggregated across every posting", async () => {
    GET.mockResolvedValue({
      data: { posted_jobs: 5, open_jobs: 4, applied: 12, shortlisted: 3, hired: 1, jobs: [JOB] },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<EmployerDashboard orgSlug="apollo-care-hospitals" />);
    expect(await screen.findByText("5")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
  });

  it("shows how workers rate the organisation, and shows nothing when nobody has", async () => {
    const base = { posted_jobs: 2, open_jobs: 2, applied: 0, shortlisted: 0, hired: 0, jobs: [JOB] };
    GET.mockResolvedValue({
      data: { ...base, rating: { average: 4.2, count: 1 } },
      error: undefined,
      response: { status: 200 },
    });
    const first = renderUi(<EmployerDashboard orgSlug="apollo-care-hospitals" />);
    expect(await screen.findByText("Workers rate you")).toBeTruthy();
    expect(screen.getByText("4.2")).toBeTruthy();
    expect(screen.getByText("1 rating")).toBeTruthy();
    first.unmount();

    // No ratings yet is not a rating of zero.
    GET.mockResolvedValue({ data: { ...base, rating: null }, error: undefined, response: { status: 200 } });
    renderUi(<EmployerDashboard orgSlug="apollo-care-hospitals" />);
    await screen.findByText("Open vacancies");
    expect(screen.queryByText("Workers rate you")).toBeNull();
  });

  it("renders a bar per vacancy and expands its pool detail on click", async () => {
    GET.mockResolvedValue({
      data: { posted_jobs: 1, open_jobs: 1, applied: 3, shortlisted: 0, hired: 0, jobs: [JOB] },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<EmployerDashboard orgSlug="apollo-care-hospitals" />);
    const bar = await screen.findByRole("button", { name: /Cashier/ });
    expect(screen.queryByText("Nearly ready")).toBeNull();
    fireEvent.click(bar);
    expect(await screen.findByText("Nearly ready")).toBeTruthy();
  });

  it("renders the empty state when there are no published vacancies", async () => {
    GET.mockResolvedValue({
      data: { posted_jobs: 0, open_jobs: 0, applied: 0, shortlisted: 0, hired: 0, jobs: [] },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<EmployerDashboard orgSlug="apollo-care-hospitals" />);
    expect(await screen.findByText("No published vacancies yet.")).toBeTruthy();
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
