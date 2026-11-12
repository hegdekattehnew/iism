import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SuggestedCourses } from "@/components/SuggestedCourses";
import type { components } from "@/lib/api-schema";
import { publicBatch } from "@/test/batch-fixtures";
import { personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

type Suggestion = components["schemas"]["CourseSuggestionOut"];

const course = (slug: string, title = slug): Suggestion => ({
  slug,
  title,
  mode: "offline",
  language: "both",
  duration_hours: 100,
  fee_inr: 1000,
  closes: ["x"],
  closes_count: 1,
  gap_size: 2,
  covers_mandatory: 1,
  location_state: null,
  location_district: null,
  starts_on: null,
  seats_left: null,
  reach: "unknown",
  started: false,
  full: false,
  within_budget: null,
  attendable: true,
});

const batchOf = (id: string, slug: string, title: string, over: Record<string, unknown> = {}) =>
  publicBatch({
    id,
    course: { ...publicBatch().course, slug, title },
    ...over,
  });

const serve = (items: unknown[]) =>
  GET.mockResolvedValue({ data: { items, total: items.length }, error: undefined });
const query = () =>
  (GET.mock.calls.at(-1)?.[1] as { params: { query: Record<string, unknown> } }).params.query;

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  world.memberships = [personal()];
});

/** Sprint 101, BL-20.2: the nearest batch of the courses that would close a match's gap. */
describe("the nearest batch of a suggested course", () => {
  it("is not asked for unless the screen wants it", async () => {
    renderUi(<SuggestedCourses courses={[course("welding")]} />);
    await new Promise((r) => setTimeout(r, 30));
    expect(GET).not.toHaveBeenCalled();
  });

  it("asks once for all the courses, and shows the first batch of each, in the server's order", async () => {
    serve([
      batchOf("b1", "welding", "Welding basics", { starts_on: "2026-11-09" }),
      batchOf("b2", "welding", "Welding basics", { starts_on: "2026-11-20" }),
      batchOf("b3", "fitting", "Fitting basics", { starts_on: "2026-11-12", reach: "state" }),
    ]);
    renderUi(
      <SuggestedCourses
        withBatches
        courses={[course("welding", "Welding basics"), course("fitting", "Fitting basics")]}
      />,
    );
    expect(await screen.findByRole("heading", { name: "Next batches of these courses" })).toBeTruthy();
    expect(GET.mock.calls.filter((c) => c[0] === "/batches")).toHaveLength(1);
    expect(query().courses).toEqual(["welding", "fitting"]);
    const links = screen.getAllByRole("link", { name: /starts/ });
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/batches/b1", "/batches/b3"]);
    expect(links[0].textContent).toContain("Welding basics: starts Nov 9, 2026 at Hadapsar Centre");
    expect(screen.queryByText(/Nov 20, 2026/)).toBeNull();
  });

  it("shows at most three, and labels how near each one is, a far one as a warning", async () => {
    serve(
      ["a", "b", "c", "d"].map((s, i) =>
        batchOf(`b${i}`, s, s.toUpperCase(), { reach: i === 1 ? "elsewhere" : "district" }),
      ),
    );
    renderUi(
      <SuggestedCourses
        withBatches
        courses={["a", "b", "c", "d"].map((s) => course(s, s.toUpperCase()))}
      />,
    );
    await screen.findByRole("heading", { name: "Next batches of these courses" });
    expect(screen.getAllByRole("link", { name: /starts/ })).toHaveLength(3);
    expect(screen.getByText("Outside your state").className).toContain("warning");
    expect(screen.getAllByText("In your district")[0].className).toContain("success");
    expect(screen.getAllByText("In your district")).toHaveLength(2);
  });

  it("says nothing for a course nobody has planned a batch of", async () => {
    serve([]);
    renderUi(<SuggestedCourses withBatches courses={[course("welding")]} />);
    await waitFor(() => expect(GET).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByRole("heading", { name: "Next batches of these courses" })).toBeNull();
    expect(screen.getByRole("link", { name: "welding" })).toBeTruthy();
  });

  it("costs the block and never the screen when the read fails", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    renderUi(<SuggestedCourses withBatches courses={[course("welding")]} />);
    await waitFor(() => expect(GET).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByRole("heading", { name: "Next batches of these courses" })).toBeNull();
    expect(screen.getByRole("link", { name: "welding" })).toBeTruthy();
  });

  it("holds its room while it loads, so what is below it does not jump", () => {
    GET.mockReturnValue(new Promise(() => undefined));
    const { container } = renderUi(<SuggestedCourses withBatches courses={[course("welding")]} />);
    const place = container.querySelector("[data-loading]");
    expect(place?.className).toContain("h-16");
  });

  it("asks for nothing when there are no courses", async () => {
    renderUi(<SuggestedCourses withBatches courses={[]} />);
    await new Promise((r) => setTimeout(r, 30));
    expect(GET).not.toHaveBeenCalled();
  });
});
