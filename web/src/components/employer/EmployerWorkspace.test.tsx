import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EmployerWorkspace } from "@/components/employer/EmployerWorkspace";
import { renderUi, resetWorld } from "@/test/harness";
import { ApiError } from "@/lib/http";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
// The **real** `@/lib/org`, with only the harness's `world`-driven pieces
// swapped in. This component's whole subject is `useOrgJobs` and
// `useOrgJobMutations`; replacing the module wholesale, as every other test
// here does, would test the mock instead of the workspace.
vi.mock("@/lib/org", async () => ({
  ...(await vi.importActual<typeof import("@/lib/org")>("@/lib/org")),
  ...(await import("@/test/harness")).orgMock,
}));
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
 * Sprint 27's employer half. A vacancy now has three states, not two, and the
 * difference between *unpublish* and *close* is the thing a wrong label here
 * would quietly destroy: unpublishing hides the vacancy, closing leaves its
 * page and its inbox and stops it taking applications.
 */

const job = (over: Record<string, unknown> = {}) => ({
  id: "j1",
  slug: "cashier",
  title: "Cashier",
  status: "published",
  is_open: true,
  positions: 1,
  closes_at: null,
  closed_at: null,
  close_reason: null,
  location_state: "Karnataka",
  location_district: "Bengaluru Urban",
  employment_type: "full_time",
  experience_min_years: 0,
  nsqf_level_min: 4,
  skills: [{ skill_slug: "till", name: "Till", importance: 5, is_mandatory: true }],
  tenant: { id: "t1", slug: "acme", name: "Acme", tenant_type: "employer" },
  ...over,
});

function world_(jobs: ReturnType<typeof job>[]) {
  GET.mockImplementation((path: string) =>
    Promise.resolve({
      data: path.includes("/jobs") ? jobs : { memberships: [] },
      error: undefined,
    }),
  );
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  POST.mockResolvedValue({ data: job(), error: undefined });
  world_([job()]);
});

describe("EmployerWorkspace — the three states of a vacancy", () => {
  it("shows an open published vacancy as published", async () => {
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    expect(await screen.findByText("Published")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Close vacancy" })).toBeTruthy();
  });

  it("shows a draft as a draft, and offers no close", async () => {
    // Closing something nobody can see is not a thing to offer.
    world_([job({ status: "draft", is_open: false })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    expect(await screen.findByText("Draft")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Close vacancy" })).toBeNull();
  });

  it("names why a closed vacancy is closed, rather than calling it a draft", async () => {
    world_([job({ is_open: false, close_reason: "filled" })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    expect(await screen.findByText("Filled")).toBeTruthy();
    expect(screen.queryByText("Draft")).toBeNull();
    expect(screen.queryByText("Published")).toBeNull();
    expect(screen.getByRole("button", { name: "Reopen" })).toBeTruthy();
  });

  it("distinguishes an expired vacancy from one the employer closed", async () => {
    world_([job({ is_open: false, close_reason: "expired" })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    expect(await screen.findByText("Expired")).toBeTruthy();
  });

  it("reopens without a confirmation, because reopening takes nothing away", async () => {
    world_([job({ is_open: false, close_reason: "withdrawn" })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    fireEvent.click(await screen.findByRole("button", { name: "Reopen" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect((POST.mock.calls[0] as [string])[0]).toBe(
      "/org/{org_slug}/jobs/{slug}/reopen",
    );
  });

  it("asks before closing, and sends the reason", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    fireEvent.click(await screen.findByRole("button", { name: "Close vacancy" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/org/{org_slug}/jobs/{slug}/close");
    expect(init.body).toEqual({ reason: "filled" });
    confirmSpy.mockRestore();
  });

  it("does not close when the employer says no", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    fireEvent.click(await screen.findByRole("button", { name: "Close vacancy" }));

    expect(POST).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });
});

describe("EmployerWorkspace — saying why a save failed", () => {
  /**
   * The reported bug: adding a vacancy failed with "Could not save. Check the
   * details and try again." and no way forward. The server had said exactly
   * what was wrong; the client threw it away.
   */
  const openEditor = async () =>
    fireEvent.click(await screen.findByRole("button", { name: "New vacancy" }));

  it("shows the field and the rule the server named", async () => {
    POST.mockRejectedValue(
      new ApiError(422, "Title: String should have at least 3 characters"),
    );
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    await openEditor();

    fireEvent.change(screen.getByLabelText(/Job title/i), { target: { value: "ab" } });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(
      await screen.findByText("Title: String should have at least 3 characters"),
    ).toBeTruthy();
    expect(screen.queryByText(/Could not save\./)).toBeNull();
  });

  it("names an unknown standard, rather than blaming the whole form", async () => {
    POST.mockRejectedValue(new ApiError(422, "Unknown standards: welding-x"));
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    await openEditor();
    fireEvent.change(screen.getByLabelText(/Job title/i), { target: { value: "Welder" } });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findByText("Unknown standards: welding-x")).toBeTruthy();
  });

  it("falls back to the generic line when the failure carried nothing", async () => {
    // A network drop or a 500 says nothing useful; the old sentence is right
    // *there* and only there.
    POST.mockRejectedValue(new ApiError(500, null));
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    await openEditor();
    fireEvent.change(screen.getByLabelText(/Job title/i), { target: { value: "Welder" } });
    fireEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(await screen.findByText(/Could not save\./)).toBeTruthy();
  });
});
