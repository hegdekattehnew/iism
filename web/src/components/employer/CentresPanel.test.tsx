import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CENTRE_STATE_LOOK, CentresPanel } from "@/components/employer/CentresPanel";
import { CheckCircleIcon, XCircleIcon } from "@/components/ui/icons";
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
  ...over,
});

function list(items: ReturnType<typeof centre>[]) {
  GET.mockResolvedValue({
    data: { items, total: items.length, active: items.filter((c) => c.status === "active").length, limit: 200 },
    error: undefined,
    response: { status: 200 },
  });
}

const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  PUT.mockReset();
});

const panel = () => renderUi(<CentresPanel org="acme" />);

/** Sprint 95, ADR-102: an organisation that delivers training calls out its centres. */
describe("CentresPanel", () => {
  it("lists each centre with its state and its own address mark, as words", async () => {
    list([
      centre(),
      centre({ slug: "acme-nagpur", name: "Nagpur", status: "closed", is_verified: true }),
    ]);
    panel();
    expect(await screen.findByText("Hadapsar")).toBeTruthy();
    expect(screen.getByText("1 open of 2")).toBeTruthy();
    expect(screen.getByText("Open")).toBeTruthy();
    expect(screen.getByText("Closed")).toBeTruthy();
    expect(screen.getByText("Address checked")).toBeTruthy();
    expect(screen.getByText("Address not checked yet")).toBeTruthy();
    expect(screen.getAllByText(/12 Main Road · Pune, Maharashtra/)).toHaveLength(2);
  });

  it("says nothing about the place being unfound when it was found, and says it when not", async () => {
    list([centre(), centre({ slug: "x", name: "Lost", place_resolved: false })]);
    panel();
    await screen.findByText("Lost");
    expect(screen.getAllByText(/could not find this place/)).toHaveLength(1);
  });

  it("draws open and closed as two different shapes, not one tone", () => {
    const shapes = new Set(
      Object.values(CENTRE_STATE_LOOK).map((l) => {
        const Icon = l.icon;
        return Icon === CheckCircleIcon ? "check" : Icon === XCircleIcon ? "x" : "other";
      }),
    );
    expect(shapes).toEqual(new Set(["check", "x"]));
  });

  it("draws a checked address and an unchecked one as different shapes and tones", async () => {
    list([centre({ is_verified: true }), centre({ slug: "b", name: "Other" })]);
    panel();
    await screen.findByText("Hadapsar");
    const checked = screen.getByText("Address checked", { selector: "span" }) as HTMLElement;
    const unchecked = screen.getByText("Address not checked yet", { selector: "span" }) as HTMLElement;
    expect(checked.querySelector("svg")!.innerHTML).not.toBe(unchecked.querySelector("svg")!.innerHTML);
    expect(checked.className).not.toBe(unchecked.className);
  });

  it("adds a centre with the fields as typed, a blank address as null", async () => {
    list([]);
    POST.mockResolvedValue(ok(centre()));
    panel();
    fireEvent.click((await screen.findAllByRole("button", { name: "Add a centre" }))[0]);
    fireEvent.change(screen.getByLabelText("Centre name"), { target: { value: "  Hadapsar  " } });
    fireEvent.change(screen.getByLabelText("State"), { target: { value: "Maharashtra" } });
    fireEvent.change(screen.getByLabelText("District"), { target: { value: "Pune" } });
    fireEvent.click(screen.getByRole("button", { name: "Add centre" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/org/{org_slug}/centres");
    expect(init.body).toEqual({
      name: "Hadapsar",
      address: null,
      state: "Maharashtra",
      district: "Pune",
    });
  });

  it("shows the server's reason beside the form when it refuses a duplicate", async () => {
    list([]);
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "This organisation already has a centre called that (acme-hadapsar)" },
      response: { status: 409 },
    });
    panel();
    fireEvent.click((await screen.findAllByRole("button", { name: "Add a centre" }))[0]);
    fireEvent.change(screen.getByLabelText("Centre name"), { target: { value: "Hadapsar" } });
    fireEvent.change(screen.getByLabelText("State"), { target: { value: "Maharashtra" } });
    fireEvent.change(screen.getByLabelText("District"), { target: { value: "Pune" } });
    fireEvent.click(screen.getByRole("button", { name: "Add centre" }));
    expect((await screen.findByRole("alert")).textContent).toContain("already has a centre");
    expect(screen.queryByText("Could not save the centre. Try again.")).toBeNull();
  });

  it("closes an open centre and reopens a closed one, each on its own route", async () => {
    list([centre(), centre({ slug: "acme-nagpur", name: "Nagpur", status: "closed" })]);
    POST.mockResolvedValue(ok(centre()));
    panel();
    await screen.findByText("Hadapsar");
    expect(screen.queryByRole("button", { name: "Reopen: Hadapsar" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Close: Nagpur" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Close: Hadapsar" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0][0]).toBe("/org/{org_slug}/centres/{centre_slug}/close");
    fireEvent.click(screen.getByRole("button", { name: "Reopen: Nagpur" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(2));
    expect(POST.mock.calls[1][0]).toBe("/org/{org_slug}/centres/{centre_slug}/reopen");
  });

  it("warns, before the change, that moving a checked centre removes the mark", async () => {
    list([centre({ is_verified: true }), centre({ slug: "b", name: "Other" })]);
    panel();
    await screen.findByText("Hadapsar");
    fireEvent.click(screen.getByRole("button", { name: "Edit: Hadapsar" }));
    expect(screen.getByText(/mark is removed until it is checked again/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "Edit: Other" }));
    expect(screen.queryByText(/mark is removed until it is checked again/)).toBeNull();
  });

  it("saves a change to the centre's own route", async () => {
    list([centre()]);
    PUT.mockResolvedValue(ok(centre({ name: "Hadapsar East" })));
    panel();
    await screen.findByText("Hadapsar");
    fireEvent.click(screen.getByRole("button", { name: "Edit: Hadapsar" }));
    fireEvent.change(screen.getByLabelText("Centre name"), { target: { value: "Hadapsar East" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(PUT).toHaveBeenCalledTimes(1));
    const [path, init] = PUT.mock.calls[0] as [
      string,
      { params: { path: { centre_slug: string } }; body: { name: string } },
    ];
    expect(path).toBe("/org/{org_slug}/centres/{centre_slug}");
    expect(init.params.path.centre_slug).toBe("acme-hadapsar");
    expect(init.body.name).toBe("Hadapsar East");
  });

  it("offers settings, not a blank list, to an organisation that does not deliver", async () => {
    GET.mockResolvedValue({ data: undefined, error: { detail: "x" }, response: { status: 403 } });
    panel();
    expect(await screen.findByText(/does not deliver training/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open settings" }).getAttribute("href")).toBe(
      "/employer/acme/settings",
    );
  });

  it("tells a signed-out owner their session ran out, not that they have no access", async () => {
    GET.mockResolvedValue({ data: undefined, error: { detail: "x" }, response: { status: 401 } });
    panel();
    await waitFor(() => expect(screen.queryByText(/do not have access/)).toBeNull());
    expect(screen.queryByText(/does not deliver training/)).toBeNull();
    expect(await screen.findByRole("link", { name: /sign in/i })).toBeTruthy();
  });

  it("invites the first centre when there are none", async () => {
    list([]);
    panel();
    const empty = await screen.findByText("No centres yet");
    expect(within(empty.parentElement as HTMLElement).getByRole("button", { name: "Add a centre" })).toBeTruthy();
  });
});
