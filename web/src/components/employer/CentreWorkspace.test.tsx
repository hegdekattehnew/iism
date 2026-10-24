import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CentreWorkspace } from "@/components/employer/CentreWorkspace";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const PUT = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), PUT: (...a: unknown[]) => PUT(...a), POST: vi.fn() },
}));

const centre = (over: Record<string, unknown> = {}) => ({
  slug: "acme-hadapsar",
  name: "Hadapsar",
  address: "12 Main Road",
  location_state: "Maharashtra",
  location_district: "Pune",
  place_resolved: true,
  status: "active",
  closed_at: null,
  is_verified: false,
  organisation: "Acme Training",
  organisation_slug: "acme",
  ...over,
});
const colleague = (over: Record<string, unknown> = {}) => ({
  user_id: "u1",
  role: "manager",
  full_name: "Asha Rao",
  email: "asha@example.org",
  since: "2026-10-01T09:00:00Z",
  is_you: true,
  ...over,
});

const overview = (over: Record<string, unknown> = {}) => ({
  drafts: 2,
  starting_soon: 3,
  running: 1,
  unfilled_seats: 14,
  unfilled_batches: 2,
  unavailable: 0,
  upcoming: [
    {
      id: "b1",
      course: { title: "Welding basics" },
      centre: { name: "Hadapsar" },
      starts_on: "2026-11-09",
      seats_left: 12,
    },
  ],
  ...over,
});

function serve(c: unknown, members: unknown[] = [colleague()], status = 200) {
  GET.mockImplementation(async (path: string) => {
    if (status !== 200) return { data: undefined, error: {}, response: { status } };
    if (path === "/org/{org_slug}/centre") return { data: c, error: undefined, response: { status } };
    if (path === "/org/{org_slug}/batches/overview")
      return { data: overview(), error: undefined, response: { status } };
    return { data: members, error: undefined, response: { status } };
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  PUT.mockReset();
});

const page = () => renderUi(<CentreWorkspace slug="acme-hadapsar" />);

/** Sprint 96, ADR-102: the person who runs a centre sees it, and nothing of the organisation. */
describe("CentreWorkspace", () => {
  it("shows the centre, whose it is, its place and whether its address has been checked", async () => {
    serve(centre());
    page();
    expect(await screen.findByText("Hadapsar")).toBeTruthy();
    expect(screen.getByText("A training centre of Acme Training")).toBeTruthy();
    expect(screen.getByText(/12 Main Road · Pune, Maharashtra/)).toBeTruthy();
    expect(screen.getByText("Open")).toBeTruthy();
    expect(screen.getByText("Address not checked yet")).toBeTruthy();
  });

  it("leads with the centre's work: the figures, then the next batch to start (Sprint 99)", async () => {
    serve(centre());
    page();
    expect(await screen.findByText("Starting this week")).toBeTruthy();
    expect(await screen.findByText("14")).toBeTruthy();
    expect(screen.getByText("in 2 batches")).toBeTruthy();
    expect(screen.getByText(/Welding basics/)).toBeTruthy();
    expect(screen.getByText(/12 seats left/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "All batches" }).getAttribute("href")).toBe(
      "/employer/acme-hadapsar/batches",
    );
  });

  it("says who runs it, naming the reader as 'you', and says who decides", async () => {
    serve(centre(), [colleague(), colleague({ user_id: "u2", is_you: false, full_name: "Ravi Iyer", email: "r@x.org" })]);
    page();
    expect(await screen.findByText("Ravi Iyer")).toBeTruthy();
    expect(screen.getAllByText(/· you/)).toHaveLength(1);
    expect(screen.getByText(/The organisation decides who runs a centre/)).toBeTruthy();
  });

  it("sends a change to the centre's own door, not the organisation's", async () => {
    serve(centre());
    PUT.mockResolvedValue({ data: centre({ name: "Hadapsar East" }), error: undefined, response: { status: 200 } });
    page();
    fireEvent.click(await screen.findByRole("button", { name: "Change the centre's details" }));
    fireEvent.change(screen.getByLabelText("Centre name"), { target: { value: "Hadapsar East" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(PUT).toHaveBeenCalledTimes(1));
    const [path, init] = PUT.mock.calls[0] as [string, { params: { path: { org_slug: string } }; body: { name: string } }];
    expect(path).toBe("/org/{org_slug}/centre");
    expect(init.params.path.org_slug).toBe("acme-hadapsar");
    expect(init.body.name).toBe("Hadapsar East");
  });

  it("warns, before the change, that a checked address loses its mark", async () => {
    serve(centre({ is_verified: true }));
    page();
    fireEvent.click(await screen.findByRole("button", { name: "Change the centre's details" }));
    expect(screen.getByText(/mark is removed until it is checked again/)).toBeTruthy();
  });

  it("offers no edit for a closed centre, and says who can reopen it", async () => {
    serve(centre({ status: "closed", closed_at: "2026-10-20T00:00:00Z" }));
    page();
    expect(await screen.findByText(/This centre is closed, so it cannot be changed/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Change the centre's details" })).toBeNull();
  });

  it("says there is no access for a centre the person does not run, and a signed-out person is told so", async () => {
    serve(null, [], 404);
    const a = page();
    expect(await screen.findByText("You do not have access to this centre.")).toBeTruthy();
    a.unmount();
    serve(null, [], 401);
    page();
    expect(await screen.findByRole("link", { name: /sign in/i })).toBeTruthy();
    expect(screen.queryByText("You do not have access to this centre.")).toBeNull();
  });
});
