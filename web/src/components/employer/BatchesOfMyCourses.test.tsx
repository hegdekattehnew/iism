import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BatchesOfMyCourses } from "@/components/employer/BatchesOfMyCourses";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const item = (over: Record<string, unknown> = {}) => ({
  course: { slug: "welding", title: "Welding basics" },
  organisation: { slug: "partner", name: "Pune Skill Partners", is_verified: false },
  batches: 4,
  open: 1,
  full: 1,
  running: 1,
  finished: 1,
  seats: 51,
  enrolled: 2,
  ...over,
});
const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

/** Sprint 99, ADR-103: a seller sees counts of how its courses are run, and nothing else. */
describe("BatchesOfMyCourses", () => {
  it("names the course and who delivers it, with counts by phase and the seats they report", async () => {
    GET.mockResolvedValue(ok({ items: [item()], total: 1 }));
    renderUi(<BatchesOfMyCourses org="seller" />);
    expect(await screen.findByRole("heading", { name: "Welding basics" })).toBeTruthy();
    expect(screen.getByText(/Delivered by Pune Skill Partners/)).toBeTruthy();
    expect(screen.getByText("4 batches")).toBeTruthy();
    for (const text of ["1 open", "1 full", "1 running", "1 finished"]) {
      expect(screen.getByText(text)).toBeTruthy();
    }
    expect(screen.getByText("2 of 51 seats marked as taken by them")).toBeTruthy();
    // An organisation that has not been reviewed is not accused: the mark is simply absent.
    expect(screen.queryByText("Reviewed by our team")).toBeNull();
    expect(screen.queryByText(/not verified|not yet/i)).toBeNull();
  });

  it("leaves out a phase with none, and says a verified deliverer is reviewed", async () => {
    GET.mockResolvedValue(
      ok({
        items: [
          item({
            batches: 1,
            open: 1,
            full: 0,
            running: 0,
            finished: 0,
            organisation: { slug: "p", name: "P", is_verified: true },
          }),
        ],
        total: 1,
      }),
    );
    renderUi(<BatchesOfMyCourses org="seller" />);
    await screen.findByText("1 batch");
    expect(screen.queryByText(/full$/)).toBeNull();
    expect(screen.queryByText(/running$/)).toBeNull();
    expect(screen.getByText("Reviewed by our team")).toBeTruthy();
  });

  it("is never offered a learner or a contact: it only draws counts", async () => {
    GET.mockResolvedValue(ok({ items: [item()], total: 1 }));
    const { container } = renderUi(<BatchesOfMyCourses org="seller" />);
    await screen.findByText("4 batches");
    expect(container.textContent ?? "").not.toMatch(/phone|email|contact info|@/i);
  });

  it("says so when none of its courses has a published batch", async () => {
    GET.mockResolvedValue(ok({ items: [], total: 0 }));
    renderUi(<BatchesOfMyCourses org="seller" />);
    expect(await screen.findByText("None of your courses has a published batch yet.")).toBeTruthy();
  });

  it("holds its place while it loads, and costs only itself when it cannot be read", async () => {
    GET.mockReturnValueOnce(new Promise(() => undefined));
    const a = renderUi(<BatchesOfMyCourses org="seller" />);
    expect(screen.getByRole("heading", { name: "How your courses are being run" })).toBeTruthy();
    expect(a.container.querySelector("[data-loading]")).toBeTruthy();
    a.unmount();
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 403 } });
    const b = renderUi(<BatchesOfMyCourses org="seller" />);
    await vi.waitFor(() => expect(b.container.querySelector("section")).toBeNull());
  });
});
