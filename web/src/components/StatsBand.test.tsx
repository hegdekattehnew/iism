import { screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StatsBand } from "@/components/StatsBand";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

/**
 * The homepage band had no test at all (Sprint 50.5).
 *
 * Its rules are the ones a buyer would catch: a figure must say what it counts, a small real
 * number must still show, a demonstration must not pass for a customer base, and nothing may be
 * a zero it does not know.
 */

const BASE = {
  standards: 21303,
  qualifications: 4424,
  criteria: 238370,
  awarding_bodies: 106,
  sectors: 43,
  states: 36,
  districts: 766,
  entry_routes: 14405,
  jobs_posted: 21,
  jobs_open: 20,
  courses: 50,
  job_seekers: 22,
  profiles: 42,
  employers: 102,
  employers_hiring: 97,
  providers: 60,
  providers_with_course: 60,
  applications: 18,
  hires: 1,
  districts_with_vacancy: 21,
  demo: false,
};

function answer(overrides: Partial<typeof BASE> = {}) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/marketplace/stats")
      return { data: { ...BASE, ...overrides } };
    return { data: undefined };
  });
}

/** The `<dd>` of the tile whose label is `label`. */
function figure(label: string): HTMLElement {
  const dt = screen.getByText(label);
  return dt.parentElement as HTMLElement;
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("StatsBand: who is here and what has been done", () => {
  it("shows both rows, people and work first", async () => {
    answer();
    renderUi(<StatsBand />);

    expect(
      await screen.findByText("Who is here, and what has been done"),
    ).toBeTruthy();
    await screen.findByText("22");
    const people = screen.getByText("Who is here, and what has been done");
    const holds = screen.getByText(
      "Built on the national framework, not a guess",
    );
    expect(
      people.compareDocumentPosition(holds) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    expect(within(figure("Job seekers")).getByText("22")).toBeTruthy();
    expect(within(figure("Employers")).getByText("102")).toBeTruthy();
    expect(within(figure("Training providers")).getByText("60")).toBeTruthy();
    expect(within(figure("Applications made")).getByText("18")).toBeTruthy();
    expect(within(figure("Hires")).getByText("1")).toBeTruthy();
    expect(
      within(figure("Districts with an open vacancy")).getByText("21"),
    ).toBeTruthy();
  });

  it("names the narrower figure underneath only when it differs", async () => {
    answer();
    renderUi(<StatsBand />);
    await screen.findByText("22");

    // 42 profiles but 22 with a declared standard; 97 of 102 employers hiring; every provider has one.
    expect(
      within(figure("Job seekers")).getByText("42 signed up"),
    ).toBeTruthy();
    expect(within(figure("Employers")).getByText("97 hiring now")).toBeTruthy();
    expect(
      within(figure("Training providers")).queryByText(
        /with a published course/,
      ),
    ).toBeNull();
  });

  it("shows no second line when the two figures are equal", async () => {
    answer({ profiles: 22, employers_hiring: 102 });
    renderUi(<StatsBand />);
    await screen.findByText("22");

    expect(within(figure("Job seekers")).queryByText(/signed up/)).toBeNull();
    expect(within(figure("Employers")).queryByText(/hiring now/)).toBeNull();
  });

  it("shows a true zero as 0 and never hides the tile", async () => {
    answer({ job_seekers: 0, profiles: 0, hires: 0, applications: 0 });
    renderUi(<StatsBand />);

    await waitFor(() =>
      expect(within(figure("Hires")).getByText("0")).toBeTruthy(),
    );
    expect(within(figure("Job seekers")).getByText("0")).toBeTruthy();
    expect(within(figure("Applications made")).getByText("0")).toBeTruthy();
  });

  it("groups digits the Indian way, the same on every figure", async () => {
    answer({ applications: 123456 });
    renderUi(<StatsBand />);
    expect(await screen.findByText("1,23,456")).toBeTruthy();
  });

  it("says so when the figures are a demonstration, and only then", async () => {
    answer({ demo: true });
    const { unmount } = renderUi(<StatsBand />);
    expect(
      await screen.findByText(
        /These figures come from a demonstration database/,
      ),
    ).toBeTruthy();
    unmount();

    answer({ demo: false });
    renderUi(<StatsBand />);
    await screen.findByText("22");
    expect(screen.queryByText(/demonstration database/)).toBeNull();
  });

  it("renders skeletons, never zeros, while loading or when the API is unreachable", async () => {
    GET.mockImplementation(async () => ({
      data: undefined,
      error: { detail: "down" },
    }));
    renderUi(<StatsBand />);

    await waitFor(() => expect(GET).toHaveBeenCalled());
    // Not a single figure: a zero here would be a lie.
    expect(screen.queryByText("0")).toBeNull();
    expect(screen.queryByText("22")).toBeNull();
  });

  it("does not offer the geography master list as a figure", async () => {
    answer();
    renderUi(<StatsBand />);
    await screen.findByText("22");
    expect(
      screen.queryByText("States and districts in our location data"),
    ).toBeNull();
    expect(screen.queryByText("36 · 766")).toBeNull();
  });

  it("lays each section out as six tiles, three across, so the rows line up", async () => {
    answer();
    const { container } = renderUi(<StatsBand />);
    await screen.findByText("22");
    const grids = container.querySelectorAll("dl");
    expect(grids).toHaveLength(2);
    for (const grid of grids) {
      expect(grid.children).toHaveLength(6);
      // Three from tablet width up. A fourth column (`lg:grid-cols-4`) made six tiles a
      // row of four and a row of two, which is the misalignment this test exists for.
      expect(grid.className).toContain("sm:grid-cols-3");
      expect(grid.className).not.toMatch(/grid-cols-4/);
    }
  });

  it("keeps a definition list made only of terms and definitions, sub-lines included", async () => {
    // `profiles > job_seekers` and the others put a sub-line under three tiles. As a `<p>` it made
    // every `<dl>` invalid HTML (axe: definition-list), and only a populated database showed it.
    answer();
    const { container } = renderUi(<StatsBand />);
    await screen.findByText("22");
    expect(screen.getByText("42 signed up")).toBeTruthy();
    for (const grid of container.querySelectorAll("dl")) {
      for (const group of grid.children) {
        for (const child of group.children) expect(["DT", "DD"]).toContain(child.tagName);
      }
    }
  });
});

