import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProviderInbox } from "@/components/employer/ProviderInbox";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const PATCH = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), PATCH: (...a: unknown[]) => PATCH(...a) },
}));

/**
 * The provider's half. This is the only screen in the provider surface that
 * names a learner, and the rules about when it may are the whole point.
 */

const learner = (over: Record<string, unknown> = {}) => ({
  interest_id: "i1",
  status: "registered",
  registered_at: "2026-09-14T09:00:00Z",
  message: "Evenings only",
  location_state: "Telangana",
  location_district: "Hyderabad",
  contact: { full_name: "Priya Sharma", phone: "+919000000012", email: null },
  ...over,
});

function answer(items: ReturnType<typeof learner>[]) {
  GET.mockResolvedValue({
    data: {
      course: { slug: "phlebotomy-refresher", title: "Phlebotomy Refresher" },
      items,
      total: items.length,
    },
    error: undefined,
  });
}

const inbox = () => <ProviderInbox org="skillbridge-institute" courseSlug="phlebotomy-refresher" />;

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  PATCH.mockReset();
  PATCH.mockResolvedValue({ error: undefined, response: { status: 200 } });
  answer([learner()]);
});

describe("ProviderInbox", () => {
  it("shows who wants the course, how to reach them and where they are", async () => {
    renderUi(inbox());
    expect(await screen.findByText("Priya Sharma")).toBeTruthy();
    expect(screen.getByText(/\+919000000012/)).toBeTruthy();
    expect(screen.getByText("Hyderabad, Telangana")).toBeTruthy();
    expect(screen.getByText("Evenings only")).toBeTruthy();
  });

  it("never scores a learner", async () => {
    // A course publishes what it teaches, not what it requires, so there is
    // nothing to rank against -- and a second scorer is what ADR-037 forbids.
    const { container } = renderUi(inbox());
    await screen.findByText("Priya Sharma");
    expect(container.textContent).not.toMatch(/% match/);
    expect(container.textContent).not.toMatch(/weighted by importance/);
  });

  it("names nobody once the learner withdraws", async () => {
    answer([
      learner({
        status: "withdrawn",
        contact: null,
        message: null,
        location_state: null,
        location_district: null,
      }),
    ]);
    const { container } = renderUi(inbox());

    expect(await screen.findByText("A learner withdrew their interest")).toBeTruthy();
    expect(container.textContent).not.toContain("Priya Sharma");
    expect(container.textContent).not.toContain("+919000000012");
    expect(container.textContent).not.toContain("Hyderabad");
    // And cannot be moved along, which would put the details back on screen.
    expect(screen.queryByRole("button", { name: "Mark as contacted" })).toBeNull();
  });

  it("marks an interest contacted", async () => {
    renderUi(inbox());
    fireEvent.click(await screen.findByRole("button", { name: "Mark as contacted" }));

    await waitFor(() => expect(PATCH).toHaveBeenCalledTimes(1));
    const [path, init] = PATCH.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/org/{org_slug}/courses/{course_slug}/interests/{interest_id}");
    expect(init.body).toEqual({ status: "contacted" });
  });

  it("does not offer to contact somebody already contacted", async () => {
    answer([learner({ status: "contacted" })]);
    renderUi(inbox());
    expect(await screen.findByText("Contacted")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Mark as contacted" })).toBeNull();
  });

  // The mutation hardcoded "contacted", so a provider had no way to record an
  // enrolment and the dashboard's enrolled tile could only be fed by seed data.
  it("marks an interest enrolled", async () => {
    renderUi(inbox());
    fireEvent.click(await screen.findByRole("button", { name: "Mark as enrolled" }));

    await waitFor(() => expect(PATCH).toHaveBeenCalledTimes(1));
    const [, init] = PATCH.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(init.body).toEqual({ status: "enrolled" });
  });

  it("offers enrolment, and only enrolment, to somebody already contacted", async () => {
    answer([learner({ status: "contacted" })]);
    renderUi(inbox());

    expect(await screen.findByRole("button", { name: "Mark as enrolled" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Mark as contacted" })).toBeNull();
  });

  it("shows an enrolled learner as enrolled, and offers no way back", async () => {
    // "Mark as contacted" used to be offered to anyone not yet contacted --
    // including somebody enrolled, who could be moved back without a word.
    answer([learner({ status: "enrolled" })]);
    renderUi(inbox());

    expect(await screen.findByText("Enrolled")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Mark as contacted" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark as enrolled" })).toBeNull();
  });

  it("names the server's reason, on the row that failed and no other", async () => {
    answer([
      learner({ interest_id: "i1" }),
      learner({
        interest_id: "i2",
        contact: { full_name: "Second Person", phone: "+919000000013", email: null },
      }),
    ]);
    PATCH.mockResolvedValue({
      error: { detail: "This interest has been withdrawn by the learner" },
      response: { status: 409 },
    });
    renderUi(inbox());

    const buttons = await screen.findAllByRole("button", { name: "Mark as enrolled" });
    fireEvent.click(buttons[0]);

    expect(
      await screen.findByText("This interest has been withdrawn by the learner"),
    ).toBeTruthy();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("says the inbox is empty rather than rendering an empty list", async () => {
    answer([]);
    renderUi(inbox());
    expect(await screen.findByText(/Nobody has registered interest/)).toBeTruthy();
  });
});
