import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplyPanel } from "@/components/ApplyPanel";
import { personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

/**
 * Sprint 43, BL-12.6. A candidate could withdraw a *rejected* application, which
 * overwrote the status with no record of what it had been, and then apply again to
 * reset the employer's decision. The server now refuses; this is the half that stops
 * the screen offering a button that can only fail.
 */

const mine = (status: string) => ({
  id: "app-1",
  status,
  message: null,
  applied_at: "2026-09-28T07:24:06Z",
  updated_at: "2026-09-28T07:24:06Z",
  job: {
    slug: "cashier-bengaluru",
    title: "Cashier",
    location_state: "Karnataka",
    location_district: "Bengaluru",
    employment_type: "full_time",
    tenant: { id: "t1", slug: "apply-co", name: "Apply Co", tenant_type: "employer" },
  },
});

const answer = (status: string) =>
  GET.mockImplementation(async (path: string) =>
    path === "/me/applications"
      ? { data: [mine(status)], error: undefined, response: { status: 200 } }
      : { data: [], error: undefined, response: { status: 200 } },
  );

const panel = () => <ApplyPanel jobSlug="cashier-bengaluru" organisation="Apply Co" />;

beforeEach(() => {
  resetWorld();
  world.memberships = [personal()];
  GET.mockReset();
  POST.mockReset();
});

describe("ApplyPanel — a decided application", () => {
  it.each(["applied", "shortlisted"])("still offers Withdraw while it is %s", async (status) => {
    answer(status);
    renderUi(panel());
    expect(await screen.findByRole("button", { name: "Withdraw" })).toBeTruthy();
    expect(screen.getByText("Applied")).toBeTruthy();
  });

  it("says it was not selected, and offers neither Withdraw nor Apply", async () => {
    answer("rejected");
    renderUi(panel());
    expect(await screen.findByText("Not selected")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Apply for this job" })).toBeNull();
    // It must not say "Applied": that is what made a rejection look undoable.
    expect(screen.queryByText("Applied")).toBeNull();
  });

  it.each([
    ["hired", "Hired"],
    ["completed", "Completed"],
    ["no_show", "Did not attend"],
  ])("offers no Withdraw once it is %s", async (status, label) => {
    answer(status);
    renderUi(panel());
    expect(await screen.findByText(label)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Withdraw" })).toBeNull();
  });

  it("explains a refusal that arrives after the page was drawn", async () => {
    // The employer rejected between this page loading and the candidate pressing it.
    answer("shortlisted");
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "x" },
      response: { status: 409 },
    });
    renderUi(panel());
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw" }));

    await waitFor(() =>
      expect(
        screen.getByText(
          "A decision has been made on this application, so it cannot be withdrawn here. Contact the employer.",
        ),
      ).toBeTruthy(),
    );
    expect(screen.queryByText("Something went wrong. Try again.")).toBeNull();
  });
});
