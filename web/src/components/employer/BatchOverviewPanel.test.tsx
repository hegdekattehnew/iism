import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BatchOverviewPanel } from "@/components/employer/BatchOverviewPanel";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const upcoming = (n: number) => ({
  id: `b${n}`,
  course: { title: `Course ${n}` },
  centre: { name: `Centre ${n}` },
  starts_on: "2026-11-09",
  seats_left: n,
});
const overview = (over: Record<string, unknown> = {}) => ({
  drafts: 2,
  starting_soon: 3,
  running: 1,
  unfilled_seats: 14,
  unfilled_batches: 2,
  unavailable: 4,
  replies_owed: 5,
  oldest_reply_owed_since: "2026-10-12T09:00:00Z",
  conversion: { registered: 20, answered: 10, enrolled: 5, attended: 2 },
  upcoming: [upcoming(1), upcoming(2), upcoming(3), upcoming(4), upcoming(5)],
  ...over,
});
const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

/** Sprint 99, BL-18.6 and BL-22.7: a delivering organisation's home leads with what needs doing. */
describe("BatchOverviewPanel", () => {
  it("shows each figure with its own label, from the server's counts", async () => {
    GET.mockResolvedValue(ok(overview()));
    renderUi(<BatchOverviewPanel org="acme" />);
    // A tile is its label and its figure in one block; wait for the figure, which arrives after it.
    const tile = async (label: string, figure: string) => {
      const text = () =>
        screen.getByText(label).closest("div")?.parentElement?.textContent ?? "";
      await vi.waitFor(() => expect(text()).toContain(figure));
      expect(text()).not.toContain("—");
    };
    await tile("Starting this week", "3");
    await tile("Waiting to be published", "2");
    await tile("Running now", "1");
    await tile("Seats still free in batches starting within two weeks", "14");
    expect(screen.getByText("in 2 batches")).toBeTruthy();
    await tile("Need a look: their course is not published", "4");
    // Sprint 100: the learners who asked and have not been answered, and since when.
    await tile("Learners waiting for a reply", "5");
    expect(screen.getByText("the longest since Oct 12, 2026")).toBeTruthy();
  });

  it("says how registrations turned out, each step from the server and as a share of the first", async () => {
    GET.mockResolvedValue(ok(overview()));
    renderUi(<BatchOverviewPanel org="acme" />);
    expect(await screen.findByText("How registrations have turned out")).toBeTruthy();
    const step = async (label: string, figure: string) => {
      const text = () => screen.getByText(label).closest("div")?.parentElement?.textContent ?? "";
      await vi.waitFor(() => expect(text()).toContain(figure));
    };
    await step("Registered", "20");
    await step("Got a reply", "10");
    await step("Enrolled", "5");
    await step("Attended", "2");
    // A share of those who registered, for each later step; the first is the whole and has none.
    expect(screen.getByText("50% of those who registered")).toBeTruthy();
    expect(screen.getByText("25% of those who registered")).toBeTruthy();
    expect(screen.getByText("10% of those who registered")).toBeTruthy();
    expect(screen.getAllByText(/of those who registered/)).toHaveLength(3);
    expect(screen.getByText(/A learner who withdrew is in none of these/)).toBeTruthy();
  });

  it("shows no share when nobody has registered, and the steps as true zeros", async () => {
    GET.mockResolvedValue(
      ok(overview({ conversion: { registered: 0, answered: 0, enrolled: 0, attended: 0 } })),
    );
    renderUi(<BatchOverviewPanel org="acme" />);
    await screen.findByText("How registrations have turned out");
    await vi.waitFor(() =>
      expect(screen.getByText("Registered").closest("div")?.parentElement?.textContent).toContain("0"),
    );
    expect(screen.queryByText(/of those who registered/)).toBeNull();
    expect(screen.queryByText(/NaN|Infinity/)).toBeNull();
  });

  it("is on the page before it arrives, with a dash and never a zero", () => {
    GET.mockReturnValue(new Promise(() => undefined));
    renderUi(<BatchOverviewPanel org="acme" />);
    expect(screen.getByText("Starting this week")).toBeTruthy();
    expect(screen.queryByText("0")).toBeNull();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(9);
  });

  it("shows a true zero as 0", async () => {
    GET.mockResolvedValue(ok(overview({ starting_soon: 0, drafts: 0, running: 0, unfilled_seats: 0, unfilled_batches: 0, unavailable: 0, replies_owed: 0, oldest_reply_owed_since: null, conversion: { registered: 0, answered: 0, enrolled: 0, attended: 0 }, upcoming: [] })));
    renderUi(<BatchOverviewPanel org="acme" />);
    await screen.findByText("in 0 batches");
    expect(screen.getAllByText("0").length).toBe(10);
    expect(screen.queryByText(/the longest since/)).toBeNull();
  });

  it("without `showNext` leaves out the next-to-start list and the link (the list is on the page)", async () => {
    GET.mockResolvedValue(ok(overview()));
    renderUi(<BatchOverviewPanel org="acme" />);
    await screen.findByText("in 2 batches");
    expect(screen.queryByText("Next to start")).toBeNull();
    expect(screen.queryByRole("link", { name: "All batches" })).toBeNull();
  });

  it("with `showNext` lists the next three that start and links to every batch", async () => {
    GET.mockResolvedValue(ok(overview()));
    renderUi(<BatchOverviewPanel org="acme" showNext />);
    expect(await screen.findByText("Course 1")).toBeTruthy();
    expect(screen.getByText("Next to start")).toBeTruthy();
    expect(screen.getByText("Course 3")).toBeTruthy();
    expect(screen.queryByText("Course 4")).toBeNull();
    expect(screen.getByText(/Centre 1 · Nov 9, 2026 · 1 seat left/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "All batches" }).getAttribute("href")).toBe("/employer/acme/batches");
  });

  it("says so when nothing is about to start, in the place the list would be", async () => {
    GET.mockResolvedValue(ok(overview({ upcoming: [] })));
    renderUi(<BatchOverviewPanel org="acme" showNext />);
    await screen.findByText("in 2 batches");
    expect(await screen.findByText("Nothing is about to start.")).toBeTruthy();
    expect(screen.queryByText("Course 1")).toBeNull();
  });

  it("holds the same room for the list before it arrives, once it has and when it is empty", async () => {
    // jsdom has no layout, so the room is read from the classes that reserve it.
    GET.mockReturnValueOnce(new Promise(() => undefined));
    const a = renderUi(<BatchOverviewPanel org="acme" showNext />);
    expect(a.container.querySelector(".min-h-\\[11rem\\]")).toBeTruthy();
    a.unmount();
    GET.mockResolvedValue(ok(overview({ upcoming: [] })));
    const b = renderUi(<BatchOverviewPanel org="acme" showNext />);
    await screen.findByText("Nothing is about to start.");
    expect(b.container.querySelector(".min-h-\\[11rem\\]")).toBeTruthy();
  });

  it("costs the block and not the page when the figures cannot be read", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 403 } });
    const { container } = renderUi(<BatchOverviewPanel org="acme" showNext />);
    await vi.waitFor(() => expect(GET).toHaveBeenCalled());
    await vi.waitFor(() => expect(container.querySelector("section")).toBeNull());
  });
});
