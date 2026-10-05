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

const invalidate = vi.fn();
vi.mock("@/lib/counts", async (original) => ({
  ...(await original<typeof import("@/lib/counts")>()),
  invalidatePublicCounts: (...a: unknown[]) => invalidate(...a),
}));

/**
 * "Applications made" is a public figure (Sprint 50.5), so applying and withdrawing both move
 * what the homepage band shows. A miss here is silent: the figure is right on the next visit and
 * wrong for everyone who navigates back, which is the "number did not move" report.
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

beforeEach(() => {
  resetWorld();
  world.memberships = [personal()];
  GET.mockReset();
  POST.mockReset();
  invalidate.mockReset();
});

describe("ApplyPanel moves the public counts", () => {
  it("when somebody applies", async () => {
    GET.mockImplementation(async () => ({ data: [], error: undefined, response: { status: 200 } }));
    POST.mockResolvedValue({
      data: { id: "app-1", status: "applied" },
      error: undefined,
      response: { status: 201 },
    });
    renderUi(<ApplyPanel jobSlug="cashier-bengaluru" organisation="Apply Co" />);

    fireEvent.click(await screen.findByRole("button", { name: "Apply for this job" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, apply" }));

    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(1));
  });

  it("when somebody withdraws", async () => {
    GET.mockImplementation(async (path: string) => ({
      data: path === "/me/applications" ? [mine("applied")] : [],
      error: undefined,
      response: { status: 200 },
    }));
    POST.mockResolvedValue({ data: undefined, error: undefined, response: { status: 204 } });
    renderUi(<ApplyPanel jobSlug="cashier-bengaluru" organisation="Apply Co" />);

    fireEvent.click(await screen.findByRole("button", { name: "Withdraw" }));

    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(1));
  });

  it("not when the server refuses", async () => {
    GET.mockImplementation(async () => ({ data: [], error: undefined, response: { status: 200 } }));
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "duplicate" },
      response: { status: 409 },
    });
    renderUi(<ApplyPanel jobSlug="cashier-bengaluru" organisation="Apply Co" />);

    fireEvent.click(await screen.findByRole("button", { name: "Apply for this job" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, apply" }));

    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(invalidate).not.toHaveBeenCalled();
  });
});
