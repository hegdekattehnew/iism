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

describe("EmployerWorkspace — saying why publishing or closing failed", () => {
  /**
   * These four buttons used to fail in two different wrong ways.
   *
   * Publish and unpublish threw a sentinel, `new Error("publish-refused")`,
   * and the screen mapped **every** failure to one fixed sentence about
   * required standards -- so an employer whose fifteen-minute token had
   * expired was told their vacancy needed a standard it already had. Close
   * and reopen had no `onError` at all: the request failed, the row still
   * said "Published", and nothing anywhere said why.
   *
   * These assert on the *server's own words*, because that is the whole point
   * -- a test that only checks "some message appeared" would pass against the
   * fixed sentence this sprint removed.
   */
  const refuse = (status: number, detail: string | null) =>
    POST.mockResolvedValue({
      data: undefined,
      error: detail === null ? {} : { detail },
      response: { status },
    });

  it("shows the refusal the server actually sent", async () => {
    refuse(422, "Add at least one required standard before publishing");
    world_([job({ status: "draft", is_open: false })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    fireEvent.click(await screen.findByRole("button", { name: "Publish" }));

    expect(
      await screen.findByText("Add at least one required standard before publishing"),
    ).toBeTruthy();
  });

  it("asks an expired session to sign in, instead of blaming the standards", async () => {
    // The defect this sprint exists for. A 401 is not a missing standard, and
    // telling somebody it is sends them to fix a vacancy that is already fine.
    refuse(401, null);
    world_([job({ status: "draft", is_open: false })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    fireEvent.click(await screen.findByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/Your session has expired/)).toBeTruthy();
    expect(screen.queryByText(/required standard/)).toBeNull();
  });

  it("says something when closing is refused, rather than leaving the row open", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    refuse(409, "This vacancy is already closed");
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    fireEvent.click(await screen.findByRole("button", { name: "Close vacancy" }));

    expect(await screen.findByText("This vacancy is already closed")).toBeTruthy();
    confirmSpy.mockRestore();
  });

  it("falls back to the generic line only when the failure carried nothing", async () => {
    refuse(500, null);
    world_([job({ status: "draft", is_open: false })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    fireEvent.click(await screen.findByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/Could not do that\./)).toBeTruthy();
  });
});

describe("EmployerWorkspace -- a vacancy an operator removed (Sprint 59)", () => {
  const removed = () =>
    job({
      status: "draft",
      is_open: false,
      close_reason: "taken_down",
      taken_down_at: "2026-10-01T09:00:00Z",
      takedown_reason: "It asked applicants to pay a fee before an interview.",
    });

  it("says it was removed, when, and why, and calls it neither a draft nor closed", async () => {
    world_([removed()]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    expect(await screen.findByText("Removed")).toBeTruthy();
    expect(screen.getByText(/Removed by our team on/)).toBeTruthy();
    expect(screen.getByText("It asked applicants to pay a fee before an interview.")).toBeTruthy();
    expect(screen.queryByText("Draft")).toBeNull();
  });

  it("offers no publish or reopen, but still lets the owner edit it", async () => {
    world_([removed()]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    await screen.findByText("Removed");
    expect(screen.queryByRole("button", { name: "Publish" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reopen" })).toBeNull();
    expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy();
  });
});

/**
 * Sprint 73, UI-15: one primary action per row, Edit beside it, the rest behind "More". The row used
 * to end in five loose text links about 20 px tall.
 */
describe("EmployerWorkspace: a row's actions", () => {
  const row = async () => (await screen.findByText("Cashier")).closest("li")!;

  it("puts the candidates first for a live vacancy and Edit beside them, both outside More", async () => {
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    const li = await row();
    const more = li.querySelector("details")!;
    expect(more.hasAttribute("open")).toBe(false); // closed until asked
    const seeCandidates = screen.getByRole("link", { name: "See candidates" });
    const edit = screen.getByRole("button", { name: "Edit" });
    expect(more.contains(seeCandidates)).toBe(false);
    expect(more.contains(edit)).toBe(false);
    expect(seeCandidates.getAttribute("href")).toBe("/employer/acme/candidates/cashier");
  });

  it("keeps unpublish, close and the public page under More, not beside the primary", async () => {
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    const more = (await row()).querySelector("details")!;
    for (const name of ["Unpublish", "Close vacancy"]) {
      expect(more.contains(screen.getByRole("button", { name }))).toBe(true);
    }
    expect(more.contains(screen.getByRole("link", { name: "View the public posting" }))).toBe(true);
  });

  it("makes Publish the primary action of a draft, and offers no candidates link", async () => {
    world_([job({ status: "draft", is_open: false })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    const li = await row();
    const publish = screen.getByRole("button", { name: "Publish" });
    expect(li.querySelector("details")?.contains(publish) ?? false).toBe(false);
    expect(screen.queryByRole("link", { name: "See candidates" })).toBeNull();
  });

  it("offers a vacancy an operator removed no primary action, only Edit", async () => {
    world_([
      job({ status: "draft", is_open: false, taken_down_at: "2026-10-01T00:00:00Z", takedown_reason: "Asks for a fee." }),
    ]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    await row();
    expect(screen.queryByRole("button", { name: "Publish" })).toBeNull();
    expect(screen.queryByRole("link", { name: "See candidates" })).toBeNull();
    expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy();
  });

  it("holds every action to the 44 px floor by using the button sizes", async () => {
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    const li = await row();
    for (const control of li.querySelectorAll("button, a[href]")) {
      expect(control.className, control.textContent ?? "").toMatch(/min-h-11/);
    }
    expect(li.querySelector("summary")!.className).toMatch(/min-h-11/);
  });
});

/** Sprint 88, BL-19.18: each state of a vacancy is a word with its own shape and tone. */
describe("EmployerWorkspace -- the look of a vacancy's state", () => {
  const chip = async (word: string) => (await screen.findByText(word, { selector: "span" })) as HTMLElement;

  it.each([
    [{}, "Published", "bg-success-surface"],
    [{ status: "draft", is_open: false }, "Draft", "bg-warning-surface"],
    [{ is_open: false, close_reason: "filled" }, "Filled", "bg-surface-muted"],
    [{ taken_down_at: "2026-10-01T00:00:00Z", takedown_reason: "x" }, "Removed", "bg-danger-surface"],
  ])("draws %j as %s on %s, with a shape", async (over, word, token) => {
    world_([job(over)]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    const el = await chip(word);
    expect(el.className).toContain(token);
    expect(el.querySelector("svg")).toBeTruthy();
  });

  it("gives the four states four different shapes", async () => {
    const shapes: string[] = [];
    for (const [over, word] of [
      [{}, "Published"],
      [{ status: "draft", is_open: false }, "Draft"],
      [{ is_open: false, close_reason: "filled" }, "Filled"],
      [{ taken_down_at: "2026-10-01T00:00:00Z", takedown_reason: "x" }, "Removed"],
    ] as const) {
      world_([job(over)]);
      const { unmount } = renderUi(<EmployerWorkspace orgSlug="acme" />);
      shapes.push((await chip(word)).querySelector("svg")!.innerHTML);
      unmount();
    }
    expect(new Set(shapes).size).toBe(4);
  });

  it("shows the place and the counts with an icon each, and no mandatory chip when none is", async () => {
    world_([job({ skills: [{ skill_slug: "till", name: "Till", importance: 5, is_mandatory: false }] })]);
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    const standards = await screen.findByText("1 required standard");
    expect(standards.querySelector("svg")).toBeTruthy();
    expect(screen.queryByText(/mandatory/)).toBeNull();
    expect(screen.getByText(/Bengaluru Urban, Karnataka/).parentElement!.querySelector("svg")).toBeTruthy();
  });

  it("shows the mandatory count as its own chip when there is one", async () => {
    renderUi(<EmployerWorkspace orgSlug="acme" />);
    const mandatory = await screen.findByText(/1 mandatory/);
    expect(mandatory.querySelector("svg")).toBeTruthy();
  });
});
