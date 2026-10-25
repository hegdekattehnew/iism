import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BatchBrowser } from "@/components/BatchBrowser";
import { NextBatches } from "@/components/NextBatches";
import { publicBatch } from "@/test/batch-fixtures";
import { personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a), POST: vi.fn() } }));

/** Sprint 100, BL-20.2: the list, its chips and its count, and the course page's block. */

const reply = (items: unknown[], total = items.length) => ({ data: { items, total }, error: undefined });

function serve(items: unknown[], total = items.length) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/batches") return reply(items, total);
    if (path === "/geography/states")
      return { data: [{ id: "27", name: "MAHARASHTRA" }], error: undefined };
    if (path === "/geography/districts")
      return { data: [{ id: "519", name: "PUNE" }], error: undefined };
    return { data: [], error: undefined };
  });
}

const batchCalls = () => GET.mock.calls.filter((c) => c[0] === "/batches");
const lastQuery = () =>
  (batchCalls().at(-1)?.[1] as { params: { query: Record<string, unknown> } }).params.query;

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  world.memberships = [personal()];
});

describe("BatchBrowser", () => {
  it("prints the server's count, not the page's length", async () => {
    serve([publicBatch()], 41);
    renderUi(<BatchBrowser />);
    expect(await screen.findByText("41 batches")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Show more (40 left)" })).toBeTruthy();
  });

  it("says plainly when nothing matches, and says what to try", async () => {
    serve([]);
    renderUi(<BatchBrowser />);
    expect(await screen.findByText("No batches to show")).toBeTruthy();
    expect(screen.getByText(/Try another state/)).toBeTruthy();
  });

  it("says it could not load, and never that there are none", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    renderUi(<BatchBrowser />);
    expect(await screen.findByText("Could not load the batches. Try again.")).toBeTruthy();
    expect(screen.queryByText("No batches to show")).toBeNull();
  });

  it("asks the server to narrow by each chip, and sends nothing for a chip left alone", async () => {
    serve([publicBatch()]);
    renderUi(<BatchBrowser />);
    await screen.findByText("1 batch");
    expect(Object.values(lastQuery()).filter((v) => v !== undefined && v !== 12 && v !== 0)).toEqual([]);

    fireEvent.change(screen.getByLabelText("Starts within"), { target: { value: "14" } });
    await waitFor(() => expect(lastQuery().starts_within).toBe(14));
    fireEvent.change(screen.getByLabelText("Fee"), { target: { value: "5000" } });
    await waitFor(() => expect(lastQuery().max_fee).toBe(5000));
    fireEvent.change(screen.getByLabelText("How it is taught"), { target: { value: "online" } });
    await waitFor(() => expect(lastQuery().mode).toBe("online"));
    expect(lastQuery().starts_within).toBe(14);
  });

  it("offers a district only once a state is chosen, and drops it when the state changes", async () => {
    serve([publicBatch()]);
    renderUi(<BatchBrowser />);
    await screen.findByText("1 batch");
    expect(screen.queryByLabelText("District")).toBeNull();
    fireEvent.change(await screen.findByLabelText("State"), { target: { value: "27" } });
    const district = await screen.findByLabelText("District");
    await screen.findByRole("option", { name: "PUNE" });
    fireEvent.change(district, { target: { value: "519" } });
    await waitFor(() => expect(lastQuery().district_id).toBe("519"));
    fireEvent.change(screen.getByLabelText("State"), { target: { value: "" } });
    await waitFor(() => expect(lastQuery().district_id).toBeUndefined());
  });

  it("keeps the course it was opened for in every request", async () => {
    serve([publicBatch()]);
    renderUi(<BatchBrowser course="welding" />);
    await screen.findByText("1 batch");
    fireEvent.change(screen.getByLabelText("Starts within"), { target: { value: "7" } });
    await waitFor(() => expect(lastQuery().starts_within).toBe(7));
    expect(lastQuery().course).toBe("welding");
  });
});

describe("NextBatches", () => {
  it("shows nothing at all for a course nobody has planned a batch of", async () => {
    serve([]);
    const { container } = renderUi(<NextBatches course="welding" />);
    await waitFor(() => expect(batchCalls().length).toBe(1));
    // The answer has to have arrived: while it is pending the block is a placeholder, also empty.
    await new Promise((r) => setTimeout(r, 30));
    expect(container.querySelector("section")).toBeNull();
    expect(container.textContent).toBe("");
  });

  it("costs the page this block and nothing else when the read fails", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    const { container } = renderUi(<NextBatches course="welding" />);
    await waitFor(() => expect(batchCalls().length).toBe(1));
    await new Promise((r) => setTimeout(r, 30));
    expect(container.textContent).toBe("");
  });

  it("asks for three of this course's batches and links to the rest when there are more", async () => {
    serve([publicBatch({ id: "a" }), publicBatch({ id: "b" })], 7);
    renderUi(<NextBatches course="welding" />);
    expect(await screen.findByRole("heading", { name: "Next batches of this course" })).toBeTruthy();
    expect(lastQuery().limit).toBe(3);
    expect(lastQuery().course).toBe("welding");
    expect(
      screen.getByRole("link", { name: "See all 7 batches of this course" }).getAttribute("href"),
    ).toBe("/batches?course=welding");
  });

  it("offers no link to more when it has shown them all", async () => {
    serve([publicBatch()], 1);
    renderUi(<NextBatches course="welding" />);
    await screen.findByRole("heading", { name: "Next batches of this course" });
    expect(screen.queryByRole("link", { name: /See all/ })).toBeNull();
  });
});
