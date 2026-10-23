import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DELIVERY_LOOK } from "@/components/cards/delivery-look";
import { DeliveryPanel } from "@/components/employer/DeliveryPanel";
import { org as orgMembership, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const other = (over: Record<string, unknown> = {}) => ({
  slug: "acme-academy",
  name: "Acme Academy",
  city: "Pune",
  is_verified: false,
  ...over,
});
const row = (over: Record<string, unknown> = {}) => ({
  id: "r1",
  state: "requested",
  side: "partner",
  initiated_by: "partner",
  other: other(),
  course: { slug: "welding", title: "Welding basics" },
  requested_at: "2026-10-20T09:00:00Z",
  approved_at: null,
  ended_at: null,
  ended_by_side: null,
  ...over,
});

function serve(asPartner: unknown[] = [], asProvider: unknown[] = []) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/org/{org_slug}/delivery")
      return { data: { as_partner: asPartner, as_provider: asProvider }, error: undefined, response: { status: 200 } };
    if (path === "/training-organisations")
      return {
        data: { items: [other(), other({ slug: "me", name: "Me Myself" })], total: 2 },
        error: undefined,
        response: { status: 200 },
      };
    if (path === "/providers/{slug}")
      return {
        data: { courses: [{ slug: "welding", title: "Welding basics" }, { slug: "plumbing", title: "Plumbing basics" }] },
        error: undefined,
        response: { status: 200 },
      };
    return { data: undefined, error: {}, response: { status: 404 } };
  });
}
const ok = (data: unknown = {}) => ({ data, error: undefined, response: { status: 200 } });

function as(delivers: boolean, sells: boolean) {
  const m = orgMembership("me", "course_provider", "Me Myself");
  m.tenant.delivers_training = delivers;
  m.tenant.publishes_courses = sells;
  world.memberships = [m];
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
});

const panel = () => renderUi(<DeliveryPanel org="me" />);

/** Sprint 97, ADR-102: who delivers whose courses, from each side of an organisation. */
describe("DeliveryPanel", () => {
  it("shows a side only for what the organisation does", async () => {
    as(true, false);
    serve();
    const a = panel();
    expect(await screen.findByText("Courses you deliver for others")).toBeTruthy();
    expect(screen.queryByText("Organisations that deliver your courses")).toBeNull();
    a.unmount();
    as(false, true);
    panel();
    expect(await screen.findByText("Organisations that deliver your courses")).toBeTruthy();
    expect(screen.queryByText("Courses you deliver for others")).toBeNull();
  });

  it("shows both for an organisation that does both", async () => {
    as(true, true);
    serve();
    panel();
    expect(await screen.findByText("Courses you deliver for others")).toBeTruthy();
    expect(screen.getByText("Organisations that deliver your courses")).toBeTruthy();
  });

  it("lets a seller approve or decline a request, and a partner only withdraw its own", async () => {
    as(true, true);
    serve([row({ id: "mine", side: "partner" })], [row({ id: "theirs", side: "provider", initiated_by: "partner", other: other({ name: "Beta Centre", slug: "beta" }) })]);
    POST.mockResolvedValue(ok(row()));
    panel();
    expect(await screen.findByRole("button", { name: "Withdraw: Acme Academy" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Approve: Acme Academy" })).toBeNull();
    // And the seller has no "withdraw" for somebody else's request: it approves or declines it.
    expect(screen.queryByRole("button", { name: "Withdraw: Beta Centre" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Approve: Beta Centre" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/delivery/{authorisation_id}/approve");
    fireEvent.click(screen.getByRole("button", { name: "Decline: Beta Centre" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(2));
    expect(POST.mock.calls[1][0]).toBe("/org/{org_slug}/delivery/{authorisation_id}/decline");
    fireEvent.click(screen.getByRole("button", { name: "Withdraw: Acme Academy" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(3));
    expect(POST.mock.calls[2][0]).toBe("/org/{org_slug}/delivery/{authorisation_id}/decline");
    expect((POST.mock.calls[2][1] as { params: { path: { authorisation_id: string } } }).params.path.authorisation_id).toBe("mine");
  });

  it("offers ending to either side of an approved arrangement, and nothing for a closed one", async () => {
    as(true, true);
    serve(
      [row({ id: "a", state: "approved", side: "partner" }), row({ id: "b", state: "declined", other: other({ name: "Gone Co" }) })],
      [row({ id: "c", state: "approved", side: "provider", other: other({ name: "Delta" }) })],
    );
    POST.mockResolvedValue(ok(row()));
    panel();
    fireEvent.click(await screen.findByRole("button", { name: "End: Acme Academy" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/delivery/{authorisation_id}/revoke");
    expect(screen.getByRole("button", { name: "End: Delta" })).toBeTruthy();
    for (const verb of ["End", "Approve", "Decline", "Withdraw"]) {
      expect(screen.queryByRole("button", { name: `${verb}: Gone Co` })).toBeNull();
    }
  });

  it("names every row button so that its visible word is inside its accessible name (WCAG 2.5.3)", async () => {
    // The browser sweep's axe rule `label-content-name-mismatch`: "End it" with the name "End: Acme"
    // failed it in CI, because the visible text was not part of the name.
    as(true, true);
    serve(
      [row({ id: "a", state: "requested" }), row({ id: "b", state: "approved", other: other({ name: "Two" }) })],
      [row({ id: "c", state: "requested", side: "provider", other: other({ name: "Three" }) }), row({ id: "d", state: "approved", side: "provider", other: other({ name: "Four" }) })],
    );
    panel();
    await screen.findByText("Four");
    const named = [...document.querySelectorAll("button[aria-label]")];
    expect(named.length).toBeGreaterThanOrEqual(5);
    for (const button of named) {
      const visible = (button.textContent ?? "").trim().toLowerCase();
      expect(visible, button.outerHTML).not.toBe("");
      expect((button.getAttribute("aria-label") ?? "").toLowerCase(), button.outerHTML).toContain(visible);
    }
  });

  it("says in words what each state means for the reader", async () => {
    as(true, false);
    serve([
      row({ id: "1", state: "requested", other: other({ name: "One" }) }),
      row({ id: "2", state: "approved", other: other({ name: "Two" }) }),
      row({ id: "3", state: "declined", other: other({ name: "Three" }) }),
      row({ id: "4", state: "revoked", other: other({ name: "Four" }) }),
    ]);
    panel();
    expect(await screen.findByText(/You asked One to let you deliver this/)).toBeTruthy();
    expect(screen.getByText(/Two lets you deliver this/)).toBeTruthy();
    expect(screen.getByText(/The request to Three is closed/)).toBeTruthy();
    expect(screen.getByText(/The arrangement with Four has ended/)).toBeTruthy();
  });

  it("names the scope: one course, or every course", async () => {
    as(true, false);
    serve([row({ id: "1" }), row({ id: "2", course: null, other: other({ name: "Two" }) })]);
    panel();
    expect(await screen.findByText("The course: Welding basics")).toBeTruthy();
    expect(screen.getByText("Every course they sell")).toBeTruthy();
  });

  it("draws the four states as four different shapes", () => {
    const drawn = Object.values(DELIVERY_LOOK).map((look) => {
      const Icon = look.icon;
      const { container, unmount } = render(<Icon />);
      const markup = container.innerHTML;
      unmount();
      return markup;
    });
    expect(Object.keys(DELIVERY_LOOK)).toHaveLength(4);
    expect(new Set(drawn).size).toBe(4);
  });

  it("finds a seller, chooses what it covers and sends the request", async () => {
    as(true, false);
    serve();
    POST.mockResolvedValue(ok(row()));
    panel();
    fireEvent.change(await screen.findByLabelText("Find the organisation that sells the courses"), {
      target: { value: "acme" },
    });
    // The person's own organisation is never offered as the one to ask.
    expect(await screen.findByRole("button", { name: /Acme Academy/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Me Myself/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Acme Academy/ }));
    await screen.findByRole("option", { name: "Welding basics" });
    fireEvent.change(screen.getByLabelText("What it covers"), { target: { value: "welding" } });
    fireEvent.click(screen.getByRole("button", { name: "Send the request" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/org/{org_slug}/delivery/requests");
    expect(init.body).toEqual({ organisation_slug: "acme-academy", course_slug: "welding" });
    expect(await screen.findByText(/nothing changes until they approve/)).toBeTruthy();
  });

  it("sends 'every course' as no course at all, and invites on its own route", async () => {
    as(false, true);
    serve();
    POST.mockResolvedValue(ok(row({ side: "provider" })));
    panel();
    fireEvent.change(await screen.findByLabelText("Find the organisation that will deliver them"), {
      target: { value: "acme" },
    });
    fireEvent.click(await screen.findByRole("button", { name: /Acme Academy/ }));
    await screen.findByLabelText("What it covers");
    fireEvent.click(screen.getByRole("button", { name: "Authorise them" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/org/{org_slug}/delivery/invitations");
    expect(init.body).toEqual({ organisation_slug: "acme-academy", course_slug: null });
  });

  it("searches for sellers on one side and for deliverers on the other", async () => {
    as(true, true);
    serve();
    panel();
    fireEvent.change(await screen.findByLabelText("Find the organisation that sells the courses"), { target: { value: "ab" } });
    fireEvent.change(screen.getByLabelText("Find the organisation that will deliver them"), { target: { value: "cd" } });
    await waitFor(() => {
      const queries = GET.mock.calls
        .filter((c) => c[0] === "/training-organisations")
        .map((c) => (c[1] as { params: { query: Record<string, unknown> } }).params.query);
      expect(queries.some((q) => q.sells === true && q.q === "ab")).toBe(true);
      expect(queries.some((q) => q.delivers === true && q.q === "cd")).toBe(true);
    });
  });

  it("does not search for a single letter", async () => {
    as(true, false);
    serve();
    panel();
    fireEvent.change(await screen.findByLabelText("Find the organisation that sells the courses"), { target: { value: "a" } });
    await new Promise((r) => setTimeout(r, 60));
    expect(GET.mock.calls.some((c) => c[0] === "/training-organisations")).toBe(false);
  });

  it("shows the server's own reason when it refuses", async () => {
    as(true, false);
    serve();
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "There is already an open arrangement for that" },
      response: { status: 409 },
    });
    panel();
    fireEvent.change(await screen.findByLabelText("Find the organisation that sells the courses"), { target: { value: "acme" } });
    fireEvent.click(await screen.findByRole("button", { name: /Acme Academy/ }));
    await screen.findByLabelText("What it covers");
    fireEvent.click(screen.getByRole("button", { name: "Send the request" }));
    expect((await screen.findByRole("alert")).textContent).toContain("already an open arrangement");
    expect(screen.queryByText("That did not work. Try again.")).toBeNull();
  });

  it("tells a signed-out owner their session ran out, not that they have no access", async () => {
    as(true, false);
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 401 } });
    panel();
    expect(await screen.findByRole("link", { name: /sign in/i })).toBeTruthy();
    expect(screen.queryByText(/do not have access/)).toBeNull();
  });

  it("says there is no access on a refusal", async () => {
    as(true, false);
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 403 } });
    panel();
    expect(await screen.findByText(/do not have access/)).toBeTruthy();
  });
});
