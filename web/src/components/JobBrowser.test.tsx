import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobBrowser } from "@/components/JobBrowser";
import { renderUi, resetWorld, world } from "@/test/harness";

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
function serve(total: number, states = [{ name: "Maharashtra", count: total }], matches?: unknown) {
  GET.mockImplementation(async (path: string, init?: { params?: { query?: Q } }) => {
    if (path === "/jobs/states") return { data: states };
    if (path === "/me/matches") return matches === undefined ? { error: {}, response: { status: 403 } } : { data: matches };
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

/** Sprint 75: newest first, now that a vacancy has a posted date. */
describe("the sort", () => {
  it("is the title by default, and says nothing about it on the wire", async () => {
    serve(30);
    renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    const first = GET.mock.calls.find((c) => c[0] === "/jobs")![1].params.query;
    expect(first.sort).toBeUndefined();
    expect((screen.getByLabelText("Sort by") as HTMLSelectElement).value).toBe("title");
  });

  it("asks for newest first from the start of the list when chosen", async () => {
    serve(60);
    renderUi(<JobBrowser />);
    fireEvent.click(await screen.findByRole("button", { name: "Show more (36 left)" }));
    await screen.findByText("Vacancy number 25");

    fireEvent.change(screen.getByLabelText("Sort by"), { target: { value: "newest" } });

    await waitFor(() => {
      const calls = GET.mock.calls.filter((c) => c[0] === "/jobs").map((c) => c[1].params.query);
      expect(calls.at(-1)).toMatchObject({ sort: "newest", offset: 0 });
    });
  });
});

const seeker = () => {
  world.memberships = [{ role: "owner", tenant: { slug: "me", name: "Me", tenant_type: "personal" } }];
};

/** Sprint 84, BL-19.15 (UI-04): a signed-in job seeker's list carries their own scores. */
describe("the match score on the list", () => {
  const scored = { items: [{ job: { slug: "job-2" }, score: 87 }, { job: { slug: "job-3" }, score: 31 }], total: 2, has_skills: true };

  it("shows a seeker the score of each vacancy they have one for, and nothing on the rest", async () => {
    seeker();
    serve(5, undefined, scored);
    renderUi(<JobBrowser />);
    expect(await screen.findByText("87% match")).toBeTruthy();
    expect(screen.getByText("31% match")).toBeTruthy();
    expect(screen.getAllByText(/% match/)).toHaveLength(2);
  });

  it("puts each score on its own vacancy's card", async () => {
    seeker();
    serve(5, undefined, scored);
    renderUi(<JobBrowser />);
    await screen.findByText("87% match");
    const card = screen.getByRole("heading", { name: "Vacancy number 2" }).closest("a")!;
    expect(card.textContent).toContain("87% match");
    const other = screen.getByRole("heading", { name: "Vacancy number 1" }).closest("a")!;
    expect(other.textContent).not.toMatch(/% match/);
  });

  it("asks the server for the matches once, with the route's own page size", async () => {
    seeker();
    serve(5, undefined, scored);
    renderUi(<JobBrowser />);
    await screen.findByText("87% match");
    const calls = GET.mock.calls.filter((c) => c[0] === "/me/matches");
    expect(calls).toHaveLength(1);
    expect(calls[0][1].params.query.limit).toBe(50);
  });

  it("asks nothing of /me/matches for a visitor, who has no score and no use for one", async () => {
    world.signedIn = false;
    serve(5, undefined, scored);
    renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    expect(GET.mock.calls.some((c) => c[0] === "/me/matches")).toBe(false);
    expect(screen.queryByText(/% match/)).toBeNull();
  });

  it("asks nothing for an organisation-only account either (the route would refuse it)", async () => {
    world.memberships = [{ role: "owner", tenant: { slug: "apollo", name: "Apollo", tenant_type: "employer" } }];
    serve(5, undefined, scored);
    renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    expect(GET.mock.calls.some((c) => c[0] === "/me/matches")).toBe(false);
  });

  it("is silent when the matches cannot be had, and the list is still the list", async () => {
    seeker();
    serve(5); // /me/matches answers an error
    renderUi(<JobBrowser />);
    expect(await screen.findByText("Vacancy number 1")).toBeTruthy();
    await waitFor(() => expect(GET.mock.calls.some((c) => c[0] === "/me/matches")).toBe(true));
    expect(screen.queryByText(/% match/)).toBeNull();
    expect(screen.queryByText(/Could not load/)).toBeNull();
  });

  it("says nothing for a seeker with no skills, who has no matches yet", async () => {
    seeker();
    serve(5, undefined, { items: [], total: 0, has_skills: false });
    renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    expect(screen.queryByText(/% match/)).toBeNull();
  });
});

/** Sprint 84, BL-19.15: the filters are one row of chips, not a column of selects. */
describe("the filter chips", () => {
  it("are one named group holding type, place and order", async () => {
    serve(5);
    renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    const group = screen.getByRole("group", { name: "Filters" });
    expect(group.querySelectorAll("select")).toHaveLength(3);
    for (const name of ["All types", "All locations", "Sort by"]) {
      expect(screen.getByRole("combobox", { name })).toBeTruthy();
    }
  });

  it("has no clear chip until something narrows the list, then has one that undoes it", async () => {
    serve(5);
    renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
    fireEvent.change(screen.getByRole("combobox", { name: "All types" }), { target: { value: "gig" } });
    const clear = await screen.findByRole("button", { name: "Clear" });
    fireEvent.click(clear);
    await waitFor(() => expect((screen.getByRole("combobox", { name: "All types" }) as HTMLSelectElement).value).toBe(""));
  });

  it("puts the search box above the row, full width", async () => {
    serve(5);
    renderUi(<JobBrowser />);
    const box = await screen.findByRole("searchbox");
    expect(box.className).toContain("w-full");
  });
});

describe("the chips say what is narrowing the list, and the card leaves room for a score", () => {
  it("draws the order chip filled once it is not the default", async () => {
    serve(5);
    renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    const chip = () => screen.getByRole("combobox", { name: "Sort by" }).parentElement as HTMLElement;
    expect(chip().className).not.toContain("bg-accent-soft");
    fireEvent.change(screen.getByRole("combobox", { name: "Sort by" }), { target: { value: "newest" } });
    expect(chip().className).toContain("bg-accent-soft");
  });

  it("reserves the score's place on every card for a seeker, before any score arrives, and not for a visitor", async () => {
    seeker();
    serve(3, undefined, { items: [], total: 0, has_skills: true });
    const view = renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    const rooms = view.container.querySelectorAll("h2");
    expect(rooms.length).toBe(3);
    for (const h of rooms) expect(h.parentElement?.className).toContain("pr-24");
    view.unmount();
    resetWorld();
    serve(3);
    const visitor = renderUi(<JobBrowser />);
    await screen.findByText("Vacancy number 1");
    for (const h of visitor.container.querySelectorAll("h2")) expect(h.parentElement?.className).not.toContain("pr-24");
  });
});
