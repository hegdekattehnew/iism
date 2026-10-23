import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BatchesPanel } from "@/components/employer/BatchesPanel";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
const PUT = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PUT: (...a: unknown[]) => PUT(...a),
  },
}));

const ok = (data: unknown = {}) => ({ data, error: undefined, response: { status: 200 } });
const refused = (status: number, detail?: string) => ({
  data: undefined,
  error: detail ? { detail } : {},
  response: { status },
});

const batch = (over: Record<string, unknown> = {}) => ({
  id: "b1",
  course: {
    slug: "welding",
    title: "Welding basics",
    fee_inr: 4000,
    available: true,
    own: false,
    provider: { slug: "seller", name: "Seller Academy", is_verified: false },
  },
  centre: {
    slug: "hadapsar",
    name: "Hadapsar Centre",
    location_district: "Pune",
    location_state: "Maharashtra",
    is_verified: false,
  },
  organisation: { slug: "me", name: "Me Myself", is_verified: false },
  label: null,
  starts_on: "2026-11-09",
  ends_on: "2026-12-09",
  seats: 20,
  enrolled: 0,
  seats_left: 20,
  interested: 0,
  mode: "in_person",
  schedule: null,
  fee_inr: null,
  fee_effective: 4000,
  fee_is_override: false,
  status: "published",
  phase: "open",
  cancel_reason: null,
  ...over,
});

const centre = (over: Record<string, unknown> = {}) => ({
  slug: "hadapsar",
  name: "Hadapsar Centre",
  status: "active",
  ...over,
});
const course = (over: Record<string, unknown> = {}) => ({
  slug: "welding",
  title: "Welding basics",
  fee_inr: 4000,
  own: false,
  provider: { slug: "seller", name: "Seller Academy", is_verified: false },
  ...over,
});

function serve(
  items: unknown[] = [],
  { total = items.length, centres = [centre()], courses = [course()] } = {},
) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/org/{org_slug}/batches")
      return ok({ items, total, limit: 25, offset: 0 });
    if (path === "/org/{org_slug}/batches/courses") return ok({ items: courses, total: courses.length });
    if (path === "/org/{org_slug}/centres")
      return ok({ items: centres, total: centres.length, active: centres.length, limit: 200 });
    return refused(404);
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  PUT.mockReset();
});

const panel = () => renderUi(<BatchesPanel org="me" />);
const more = () => {
  // The secondary actions live behind a native "More"; opening it is a click on its summary.
  const summary = screen.queryByText("More", { selector: "summary" });
  if (summary) fireEvent.click(summary);
};

/** Sprint 98, ADR-103: an organisation's batches, and what each phase allows next. */
describe("BatchesPanel", () => {
  it("counts what the server says matches, not the rows loaded, and offers the rest", async () => {
    serve([batch()], { total: 3 });
    panel();
    expect(await screen.findByText("3 batches")).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Show more (2 left)" }));
    await waitFor(() => {
      const paged = GET.mock.calls.filter((c) => c[0] === "/org/{org_slug}/batches");
      expect(paged.at(-1)?.[1].params.query.offset).toBe(1);
    });
  });

  it("has no 'Show more' once everything is loaded", async () => {
    serve([batch()], { total: 1 });
    panel();
    expect(await screen.findByText("1 batch")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Show more/ })).toBeNull();
  });

  it("filters by phase on the server and says so when nothing is like that", async () => {
    serve([batch()]);
    panel();
    await screen.findByText("Welding basics");
    serve([], { total: 0 });
    fireEvent.change(screen.getByRole("combobox", { name: "Show batches" }), {
      target: { value: "cancelled" },
    });
    expect(await screen.findByText("No batches like this")).toBeTruthy();
    const last = GET.mock.calls.filter((c) => c[0] === "/org/{org_slug}/batches").at(-1);
    expect(last?.[1].params.query.phase).toBe("cancelled");
  });

  it("says there are none yet, with the way to plan one", async () => {
    serve([]);
    panel();
    expect(await screen.findByText("No batches yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Plan a batch" })).toBeTruthy();
  });

  it("publishes a draft, named for its row", async () => {
    serve([batch({ status: "draft", phase: "draft" })]);
    POST.mockResolvedValue(ok(batch()));
    panel();
    fireEvent.click(await screen.findByRole("button", { name: "Publish: Welding basics" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/batches/{batch_id}/publish");
    expect(POST.mock.calls[0][1].params.path.batch_id).toBe("b1");
  });

  it("offers a published batch Edit and Cancel but not Publish", async () => {
    serve([batch()]);
    panel();
    await screen.findByText("Welding basics");
    more();
    expect(screen.getByRole("button", { name: "Edit: Welding basics" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cancel batch: Welding basics" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Publish/ })).toBeNull();
  });

  it.each(["running", "finished", "cancelled"] as const)(
    "offers a %s batch nothing: a class in progress is never stopped",
    async (phase) => {
      serve([batch({ phase, status: phase === "cancelled" ? "cancelled" : "published", cancel_reason: phase === "cancelled" ? "by_organisation" : null })]);
      panel();
      await screen.findByText("Welding basics");
      more();
      for (const name of ["Publish", "Edit", "Cancel batch"]) {
        expect(screen.queryByRole("button", { name: new RegExp(`^${name}`) })).toBeNull();
      }
    },
  );

  it("asks before cancelling, and says how many learners will be told", async () => {
    serve([batch({ interested: 2 })]);
    POST.mockResolvedValue(ok(batch({ phase: "cancelled", status: "cancelled" })));
    panel();
    await screen.findByText("Welding basics");
    more();
    fireEvent.click(screen.getByRole("button", { name: "Cancel batch: Welding basics" }));
    expect(screen.getByText(/2 learners who registered will be told/)).toBeTruthy();
    expect(POST).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Yes, cancel it" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/batches/{batch_id}/cancel");
  });

  it("says nobody registered when nobody did, and can be backed out of", async () => {
    serve([batch()]);
    panel();
    await screen.findByText("Welding basics");
    more();
    fireEvent.click(screen.getByRole("button", { name: "Cancel batch: Welding basics" }));
    expect(screen.getByText(/Nobody has registered for it/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
    expect(screen.queryByRole("button", { name: "Yes, cancel it" })).toBeNull();
    expect(POST).not.toHaveBeenCalled();
  });

  it("shows the server's own words when a publication is refused", async () => {
    serve([batch({ status: "draft", phase: "draft" })]);
    POST.mockResolvedValue(refused(403, "This organisation is not authorised to deliver that course."));
    panel();
    fireEvent.click(await screen.findByRole("button", { name: "Publish: Welding basics" }));
    expect(await screen.findByText(/not authorised to deliver that course/)).toBeTruthy();
  });

  it("plans a batch: the course and centre are chosen, the numbers are numbers, an empty fee is none", async () => {
    serve([]);
    POST.mockResolvedValue(ok(batch()));
    panel();
    fireEvent.click(await screen.findByRole("button", { name: "Plan a batch" }));
    fireEvent.change(await screen.findByLabelText("Course"), { target: { value: "welding" } });
    fireEvent.change(screen.getByLabelText("Centre"), { target: { value: "hadapsar" } });
    fireEvent.change(screen.getByLabelText("First day"), { target: { value: "2026-11-09" } });
    fireEvent.change(screen.getByLabelText("Last day"), { target: { value: "2026-12-09" } });
    fireEvent.change(screen.getByLabelText("Seats"), { target: { value: "25" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan batch" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/batches");
    expect(POST.mock.calls[0][1].body).toEqual({
      course_slug: "welding",
      centre_slug: "hadapsar",
      label: null,
      starts_on: "2026-11-09",
      ends_on: "2026-12-09",
      seats: 25,
      mode: "in_person",
      schedule: null,
      fee_inr: null,
    });
  });

  it("offers a course that another organisation sells with its seller named", async () => {
    serve([]);
    panel();
    fireEvent.click(await screen.findByRole("button", { name: "Plan a batch" }));
    expect(await screen.findByRole("option", { name: "Welding basics (by Seller Academy)" })).toBeTruthy();
  });

  it("offers a closed centre nowhere to plan", async () => {
    serve([], { centres: [centre({ status: "closed" })] });
    panel();
    expect(await screen.findByText(/You need an open centre/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Plan a batch" })).toBeNull();
    expect(screen.getByRole("link", { name: "Open centres" }).getAttribute("href")).toBe("/employer/me/centres");
  });

  it("says what to do when there is no course to teach", async () => {
    serve([], { courses: [] });
    panel();
    expect(await screen.findByText(/no course to teach yet/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Plan a batch" })).toBeNull();
    expect(screen.getByRole("link", { name: "Open delivery" }).getAttribute("href")).toBe("/employer/me/delivery");
  });

  it("edits a batch with the course and centre fixed, and sends only what can change", async () => {
    serve([batch({ status: "draft", phase: "draft" })]);
    PUT.mockResolvedValue(ok(batch()));
    panel();
    await screen.findByText("Welding basics");
    more();
    fireEvent.click(screen.getByRole("button", { name: "Edit: Welding basics" }));
    expect(screen.queryByLabelText("Course")).toBeNull();
    expect(screen.getByText(/cannot be changed: plan a new batch instead/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Seats"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(PUT).toHaveBeenCalledTimes(1));
    const body = PUT.mock.calls[0][1].body;
    expect(body.seats).toBe(30);
    expect("course_slug" in body).toBe(false);
    expect("centre_slug" in body).toBe(false);
  });

  it("locks the dates, and says why, once learners have registered for them", async () => {
    serve([batch({ interested: 3 })]);
    panel();
    await screen.findByText("Welding basics");
    more();
    fireEvent.click(screen.getByRole("button", { name: "Edit: Welding basics" }));
    expect((screen.getByLabelText("First day") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText("Last day") as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText(/cancel this batch and plan a new one/)).toBeTruthy();
  });

  it("leaves the dates free on a draft with nobody registered", async () => {
    serve([batch({ status: "draft", phase: "draft", interested: 0 })]);
    panel();
    await screen.findByText("Welding basics");
    more();
    fireEvent.click(screen.getByRole("button", { name: "Edit: Welding basics" }));
    expect((screen.getByLabelText("First day") as HTMLInputElement).disabled).toBe(false);
  });

  it("says a seller that does not deliver has no batches, and where to change that", async () => {
    GET.mockResolvedValue(refused(403));
    panel();
    expect(await screen.findByText(/does not deliver training/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open settings" }).getAttribute("href")).toBe("/employer/me/settings");
  });

  it("tells an expired sign-in from a missing permission", async () => {
    GET.mockResolvedValue(refused(401));
    panel();
    expect(await screen.findByText(/session/i)).toBeTruthy();
    expect(screen.queryByText(/does not deliver training/)).toBeNull();
  });

  it("says plainly when the caller has no access", async () => {
    GET.mockResolvedValue(refused(404));
    panel();
    expect(await screen.findByText(/do not have access to this organisation's batches/)).toBeTruthy();
  });

  it("holds the list's place with a placeholder while it loads", () => {
    GET.mockReturnValue(new Promise(() => undefined));
    const { container } = panel();
    expect(container.querySelector("[data-loading]")).toBeTruthy();
  });

  it("keeps every row's own actions inside its card", async () => {
    serve([batch({ id: "a", status: "draft", phase: "draft" }), batch({ id: "b", course: { ...batch().course, title: "Plumbing basics" } })]);
    panel();
    const first = (await screen.findByRole("heading", { name: "Welding basics" })).closest("li") as HTMLElement;
    expect(within(first).getByRole("button", { name: "Publish: Welding basics" })).toBeTruthy();
    const second = screen.getByRole("heading", { name: "Plumbing basics" }).closest("li") as HTMLElement;
    expect(within(second).queryByRole("button", { name: /^Publish/ })).toBeNull();
  });
});
