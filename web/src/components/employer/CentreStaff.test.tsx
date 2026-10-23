import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { INVITE_LOOK, CentreStaff } from "@/components/employer/CentreStaff";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
const DELETE = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    DELETE: (...a: unknown[]) => DELETE(...a),
  },
}));

const manager = (over: Record<string, unknown> = {}) => ({
  user_id: "u1",
  role: "manager",
  full_name: "Asha Rao",
  email: "asha@example.org",
  since: "2026-10-01T09:00:00Z",
  is_you: false,
  ...over,
});
const invitation = (over: Record<string, unknown> = {}) => ({
  id: "i1",
  email: "ravi@example.org",
  role: "manager",
  state: "pending",
  expires_at: "2026-10-30T09:00:00Z",
  created_at: "2026-10-23T09:00:00Z",
  invited_by: "Priya",
  ...over,
});

function staff(managers: unknown[] = [], invitations: unknown[] = []) {
  GET.mockResolvedValue({ data: { managers, invitations }, error: undefined, response: { status: 200 } });
}
const ok = (data: unknown = undefined) => ({ data, error: undefined, response: { status: 200 } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  DELETE.mockReset();
});

const panel = (closed = false) => renderUi(<CentreStaff org="acme" centre="acme-hadapsar" closed={closed} />);

/** Sprint 96, ADR-102: the organisation decides who runs a centre. */
describe("CentreStaff", () => {
  it("lists the managers and every invitation, each state a word with its own shape", async () => {
    staff(
      [manager()],
      [
        invitation({ id: "a", state: "pending", email: "a@x.org" }),
        invitation({ id: "b", state: "accepted", email: "b@x.org" }),
        invitation({ id: "c", state: "revoked", email: "c@x.org" }),
        invitation({ id: "d", state: "expired", email: "d@x.org" }),
      ],
    );
    panel();
    expect(await screen.findByText("Asha Rao")).toBeTruthy();
    const words = ["Waiting", "Accepted", "Withdrawn", "Expired"].map(
      (w) => screen.getByText(w, { selector: "span" }) as HTMLElement,
    );
    expect(new Set(words.map((w) => w.querySelector("svg")!.innerHTML)).size).toBe(4);
    expect(Object.keys(INVITE_LOOK)).toHaveLength(4);
  });

  it("asks for a manager by the address typed, lower-cased, and clears the box", async () => {
    staff();
    POST.mockResolvedValue(ok(invitation()));
    panel();
    const box = (await screen.findByLabelText("Ask somebody to run it")) as HTMLInputElement;
    fireEvent.change(box, { target: { value: "  Ravi@Example.ORG " } });
    fireEvent.click(screen.getByRole("button", { name: "Send the invitation" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [
      string,
      { params: { path: Record<string, string> }; body: { email: string } },
    ];
    expect(path).toBe("/org/{org_slug}/centres/{centre_slug}/managers");
    expect(init.params.path).toEqual({ org_slug: "acme", centre_slug: "acme-hadapsar" });
    expect(init.body).toEqual({ email: "ravi@example.org" });
    await waitFor(() => expect(box.value).toBe(""));
  });

  it("holds the button until there is an address", async () => {
    staff();
    panel();
    const send = await screen.findByRole("button", { name: "Send the invitation" });
    expect(send).toHaveProperty("disabled", true);
  });

  it("shows the server's own reason when it refuses", async () => {
    staff();
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "There is already an invitation open for that address" },
      response: { status: 409 },
    });
    panel();
    fireEvent.change(await screen.findByLabelText("Ask somebody to run it"), {
      target: { value: "ravi@example.org" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send the invitation" }));
    expect((await screen.findByRole("alert")).textContent).toContain("already an invitation open");
    expect(screen.queryByText("That did not work. Try again.")).toBeNull();
  });

  it("removes a manager and withdraws a waiting invitation, each on its own route", async () => {
    staff([manager()], [invitation(), invitation({ id: "done", state: "accepted", email: "d@x.org" })]);
    DELETE.mockResolvedValue(ok());
    panel();
    fireEvent.click(await screen.findByRole("button", { name: "Remove: Asha Rao" }));
    await waitFor(() => expect(DELETE).toHaveBeenCalledTimes(1));
    expect(DELETE.mock.calls[0][0]).toBe("/org/{org_slug}/centres/{centre_slug}/managers/{user_id}");
    fireEvent.click(screen.getByRole("button", { name: "Withdraw: ravi@example.org" }));
    await waitFor(() => expect(DELETE).toHaveBeenCalledTimes(2));
    expect(DELETE.mock.calls[1][0]).toBe(
      "/org/{org_slug}/centres/{centre_slug}/managers/invitations/{invitation_id}",
    );
    // An accepted invitation cannot be withdrawn: there is nothing to withdraw.
    expect(screen.queryByRole("button", { name: "Withdraw: d@x.org" })).toBeNull();
  });

  it("offers no invitation form for a closed centre, and says why", async () => {
    staff([manager()]);
    panel(true);
    await screen.findByText("Asha Rao");
    expect(screen.queryByLabelText("Ask somebody to run it")).toBeNull();
    expect(screen.getByText(/Reopen it before asking anyone/)).toBeTruthy();
  });

  it("says nobody has been asked yet, rather than showing an empty box", async () => {
    staff();
    panel();
    expect(await screen.findByText(/Nobody has been asked to run this centre yet/)).toBeTruthy();
  });

  it("says it could not load, rather than showing nobody", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    panel();
    expect(await screen.findByText(/Could not load who runs this centre/)).toBeTruthy();
    expect(screen.queryByText(/Nobody has been asked/)).toBeNull();
  });
});
