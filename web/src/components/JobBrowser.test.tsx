import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobBrowser } from "@/components/JobBrowser";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const job = (n: number) => ({
  slug: `job-${n}`,
  title: `Vacancy number ${n}`,
  location_state: "Maharashtra",
  location_district: "Pune",
  employment_type: "full_time",
  experience_min_years: 0,
  salary_min_inr: 180000,
  salary_max_inr: 240000,
  tenant: { name: "Acme", is_verified: false },
});

type Q = { offset?: number; limit?: number; location_state?: string };

/** A catalogue of `total` vacancies, served the way the API does: a window and the full total. */
function serve(total: number, states = [{ name: "Maharashtra", count: total }]) {
  GET.mockImplementation(async (path: string, init?: { params?: { query?: Q } }) => {
    if (path === "/jobs/states") return { data: states };
    const q = init?.params?.query ?? {};
    const offset = q.offset ?? 0;
    const limit = q.limit ?? 50;
    const items = Array.from({ length: Math.max(0, Math.min(limit, total - offset)) }, (_, i) =>
      job(offset + i + 1),
    );
    return { data: { items, total, limit, offset } };
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

/**
 * Sprint 69, UI-06. The list asked for 200 rows once and printed their number as the count; with
 * 148 seeded jobs nobody saw it fail, and at 201 the 201st vacancy simply did not exist.
 */
describe("the vacancy list pages and counts from the server", () => {
  it("asks for a page, not for everything", async () => {
    serve(148);
    renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    const jobCalls = GET.mock.calls.filter((c) => c[0] === "/jobs");
    expect(jobCalls[0][1].params.query.limit).toBe(24);
    expect(jobCalls[0][1].params.query.limit).not.toBe(200);
  });

  it("says the server's total, not the number of rows it has loaded", async () => {
    serve(148);
    renderUi(<JobBrowser />);
    expect(await screen.findByText("148 jobs")).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(24);
  });

  it("offers the rest and says how many are left", async () => {
    serve(148);
    renderUi(<JobBrowser />);
    expect(await screen.findByRole("button", { name: "Show more (124 left)" })).toBeTruthy();
  });

  it("loads the next window by offset, and the total does not change", async () => {
    serve(148);
    renderUi(<JobBrowser />);
    fireEvent.click(await screen.findByRole("button", { name: "Show more (124 left)" }));
    await screen.findByText("Vacancy number 25");
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(48);
    expect(screen.getByText("148 jobs")).toBeTruthy();
    const offsets = GET.mock.calls.filter((c) => c[0] === "/jobs").map((c) => c[1].params.query.offset);
    expect(offsets).toEqual([0, 24]);
  });

  it("has no button when everything fits on the first page", async () => {
    serve(5);
    renderUi(<JobBrowser />);
    await screen.findByText("5 jobs");
    expect(screen.queryByRole("button", { name: /Show more/ })).toBeNull();
  });

  it("keeps the rows and offers a retry when the next page fails", async () => {
    serve(60);
    renderUi(<JobBrowser />);
    const more = await screen.findByRole("button", { name: "Show more (36 left)" });
    const answer = GET.getMockImplementation()!;
    GET.mockImplementation(async (path: string, init?: { params?: { query?: Q } }) =>
      path === "/jobs" && (init?.params?.query?.offset ?? 0) > 0
        ? { data: undefined, error: {}, response: { status: 500 } }
        : answer(path, init),
    );
    fireEvent.click(more);
    expect(await screen.findByText(/Could not load more/)).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(24);
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("does not claim 'no jobs' when the first page failed", async () => {
    GET.mockImplementation(async (path: string) =>
      path === "/jobs/states"
        ? { data: [] }
        : { data: undefined, error: {}, response: { status: 500 } },
    );
    renderUi(<JobBrowser />);
    expect(await screen.findByText(/Could not reach the API/)).toBeTruthy();
    expect(screen.queryByText("No jobs matched. Try clearing a filter.")).toBeNull();
  });
});

describe("the state filter", () => {
  it("is the catalogue's own list, with counts, not whatever the first page happened to hold", async () => {
    serve(148, [
      { name: "Maharashtra", count: 24 },
      { name: "Tamil Nadu", count: 19 },
    ]);
    renderUi(<JobBrowser />);
    expect(await screen.findByRole("option", { name: "Tamil Nadu (19)" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Maharashtra (24)" })).toBeTruthy();
  });

  it("filters by the chosen state and starts again from the first window", async () => {
    serve(148, [{ name: "Maharashtra", count: 24 }]);
    renderUi(<JobBrowser />);
    fireEvent.click(await screen.findByRole("button", { name: "Show more (124 left)" }));
    await screen.findByText("Vacancy number 25");
    const select = screen.getByRole("combobox", { name: "All locations" });
    await screen.findByRole("option", { name: "Maharashtra (24)" });
    fireEvent.change(select, { target: { value: "Maharashtra" } });
    await waitFor(() => {
      const last = GET.mock.calls.filter((c) => c[0] === "/jobs").at(-1)![1].params.query;
      expect(last.location_state).toBe("Maharashtra");
      expect(last.offset).toBe(0);
    });
  });
});
