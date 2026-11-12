import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BatchLearners } from "@/components/employer/BatchLearners";
import type { Batch } from "@/lib/batches";
import { batchLearner } from "@/test/batch-fixtures";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const PATCH = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), PATCH: (...a: unknown[]) => PATCH(...a) },
}));

const batch = (phase = "open") => ({ id: "b1", phase }) as unknown as Batch;
const serve = (items: unknown[]) =>
  GET.mockResolvedValue({ data: { items, total: items.length }, error: undefined });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  PATCH.mockReset();
  PATCH.mockResolvedValue({
    data: { interest_id: "i1", status: "contacted" },
    error: undefined,
    response: { status: 200 },
  });
});

/** Sprint 100, BL-18.7: the centre's side of a learner's interest. */
describe("BatchLearners", () => {
  it("says so when nobody has registered", async () => {
    serve([]);
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    expect(await screen.findByText("Nobody has registered interest yet.")).toBeTruthy();
  });

  it("is a refusal's silence, not an error page, when the server says this is not yours", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 403 } });
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    expect(await screen.findByText(/You do not have access/)).toBeTruthy();
  });

  it("asks a signed-out person to sign in, never 'no access'", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 401 } });
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    await waitFor(() => expect(screen.queryByText(/You do not have access/)).toBeNull());
    expect((await screen.findByRole("link", { name: /sign in/i })).getAttribute("href")).toBe("/signin");
  });

  it("shows what the learner chose to share, and how long they have waited", async () => {
    serve([batchLearner({ message: "Evenings only" })]);
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    expect(await screen.findByText("Asha Rao")).toBeTruthy();
    expect(screen.getByText("+919800000001 · asha@example.com")).toBeTruthy();
    expect(screen.getByText("Pune, Maharashtra")).toBeTruthy();
    expect(screen.getByText("Evenings only")).toBeTruthy();
    expect(screen.getByText(/waiting \d+ days?/)).toBeTruthy();
    expect(screen.getByText("Waiting for a reply", { selector: "span" })).toBeTruthy();
  });

  it("does not say 'waiting 0 days' about somebody who registered a moment ago", async () => {
    serve([batchLearner({ registered_at: new Date().toISOString() })]);
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    await screen.findByText("Asha Rao");
    expect(screen.getByText(/^Registered /)).toBeTruthy();
    expect(screen.queryByText(/waiting/)).toBeNull();
  });

  it("shows no details and offers no action for a learner who withdrew", async () => {
    serve([
      batchLearner({ status: "withdrawn", contact: null, message: null, location_district: null, location_state: null }),
    ]);
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    expect(await screen.findByText("A learner")).toBeTruthy();
    expect(screen.getByText(/This learner withdrew/)).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText(/asha@example.com/)).toBeNull();
  });

  it("offers contacted and enrolled to a waiting learner, and sends the id and the status", async () => {
    serve([batchLearner({ interest_id: "i7" })]);
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    expect(await screen.findByRole("button", { name: "Enrolled: Asha Rao" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Attended:/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Contacted: Asha Rao" }));
    await waitFor(() => expect(PATCH).toHaveBeenCalledTimes(1));
    const [path, init] = PATCH.mock.calls[0] as [
      string,
      { params: { path: Record<string, string> }; body: { status: string } },
    ];
    expect(path).toBe("/org/{org_slug}/batches/{batch_id}/learners/{interest_id}");
    expect(init.params.path).toEqual({ org_slug: "centre-1", batch_id: "b1", interest_id: "i7" });
    expect(init.body).toEqual({ status: "contacted" });
  });

  it("does not offer 'contacted' again once they have been", async () => {
    serve([batchLearner({ status: "contacted" })]);
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    await screen.findByText("Asha Rao");
    expect(screen.queryByRole("button", { name: /Contacted:/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Enrolled: Asha Rao" })).toBeTruthy();
  });

  it("offers 'attended' to an enrolled learner only once the batch has started", async () => {
    serve([batchLearner({ status: "enrolled" })]);
    const before = renderUi(<BatchLearners org="centre-1" batch={batch("open")} />);
    await screen.findByText("Asha Rao");
    expect(screen.queryByRole("button", { name: /Attended:/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Enrolled:/ })).toBeNull();
    before.unmount();
    renderUi(<BatchLearners org="centre-1" batch={batch("running")} />);
    expect(await screen.findByRole("button", { name: "Attended: Asha Rao" })).toBeTruthy();
  });

  it("never offers 'attended' to a learner who has not been enrolled, even once it has started", async () => {
    serve([batchLearner({ status: "registered" }), batchLearner({ interest_id: "i2", status: "contacted" })]);
    renderUi(<BatchLearners org="centre-1" batch={batch("running")} />);
    await screen.findAllByText("Asha Rao");
    expect(screen.queryByRole("button", { name: /Attended:/ })).toBeNull();
  });

  it("offers nothing on a cancelled batch", async () => {
    serve([batchLearner()]);
    renderUi(<BatchLearners org="centre-1" batch={batch("cancelled")} />);
    await screen.findByText("Asha Rao");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows the server's refusal in its own words", async () => {
    serve([batchLearner()]);
    PATCH.mockResolvedValue({
      data: undefined,
      error: { detail: "No seats left in this batch" },
      response: { status: 409 },
    });
    renderUi(<BatchLearners org="centre-1" batch={batch()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Enrolled: Asha Rao" }));
    expect((await screen.findByRole("alert")).textContent).toContain("No seats left in this batch");
  });
});
