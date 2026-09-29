import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamPanel } from "@/components/employer/TeamPanel";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
const PATCH = vi.fn();
const DELETE = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PATCH: (...a: unknown[]) => PATCH(...a),
    DELETE: (...a: unknown[]) => DELETE(...a),
  },
}));

/**
 * Sprint 25's screen. What it renders is decided entirely by the caller's own
 * role, and getting that wrong is invisible to `tsc` -- which is the whole
 * reason `web/` has a test runner (Sprint 18).
 */

const member = (over: Record<string, unknown> = {}) => ({
  user_id: "u1",
  role: "owner",
  full_name: "Priya Sharma",
  email: "priya@apollo-care.example",
  since: "2026-09-01T09:00:00Z",
  is_you: true,
  ...over,
});

const colleague = member({
  user_id: "u2",
  role: "member",
  full_name: "Rahul Verma",
  email: "rahul@apollo-care.example",
  is_you: false,
});

function world_(members: ReturnType<typeof member>[], invitations: unknown[] = []) {
  GET.mockImplementation((path: string) =>
    Promise.resolve({
      data: path === "/org/{org_slug}/members" ? members : invitations,
      error: undefined,
    }),
  );
}

const panel = () => <TeamPanel org="apollo-care" />;

beforeEach(() => {
  resetWorld();
  [GET, POST, PATCH, DELETE].forEach((m) => m.mockReset());
  POST.mockResolvedValue({
    data: { id: "i1", email: "new@apollo-care.example", role: "member", state: "pending" },
    error: undefined,
    response: { status: 201 },
  });
  PATCH.mockResolvedValue({ error: undefined, response: { status: 200 } });
  DELETE.mockResolvedValue({ error: undefined, response: { status: 204 } });
  world_([member(), colleague]);
});

describe("TeamPanel — what each role is offered", () => {
  it("shows an owner the members, and the controls to manage them", async () => {
    renderUi(panel());
    expect(await screen.findByText("Priya Sharma")).toBeTruthy();
    expect(screen.getByText("Rahul Verma")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send invitation" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove" })).toBeTruthy();
  });

  it("offers a plain member no controls at all", async () => {
    // `MEMBER_MANAGE` is the owner's and `MEMBER_INVITE` the admin's, so a
    // member sees colleagues and nothing to press. A button that 403s is the
    // Sprint 14 defect, and it is worse than no button.
    world_([member({ role: "member" }), colleague]);
    renderUi(panel());
    await screen.findByText("Priya Sharma");

    expect(screen.queryByRole("button", { name: "Send invitation" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
    expect(screen.getByText(/Only an owner can change roles/)).toBeTruthy();
  });

  it("lets an admin invite a member but never an admin", async () => {
    world_([member({ role: "admin" }), colleague]);
    renderUi(panel());
    await screen.findByRole("button", { name: "Send invitation" });

    const roleSelect = screen.getAllByRole("combobox").at(-1)!;
    const options = [...roleSelect.querySelectorAll("option")].map((o) => o.value);
    expect(options).toEqual(["member"]);
    // ...and cannot change anybody's role.
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
  });

  it("never offers to remove yourself, only to leave", async () => {
    renderUi(panel());
    await screen.findByText("Priya Sharma");

    // One Remove button, and it belongs to the colleague.
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Leave this organisation" })).toBeTruthy();
  });
});

describe("TeamPanel — inviting", () => {
  it("sends the address and role", async () => {
    renderUi(panel());
    fireEvent.change(await screen.findByPlaceholderText("name@organisation.in"), {
      target: { value: "New.Person@Apollo-Care.example" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/org/{org_slug}/invitations");
    // Lowercased on the way out, as every address in this product is: one
    // mailbox must not become two invitations.
    expect(init.body).toEqual({ email: "new.person@apollo-care.example", role: "member" });
  });

  it("says what went wrong rather than sitting there", async () => {
    POST.mockResolvedValue({ data: undefined, error: { detail: "x" }, response: { status: 409 } });
    renderUi(panel());
    fireEvent.change(await screen.findByPlaceholderText("name@organisation.in"), {
      target: { value: "dup@apollo-care.example" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));

    expect(
      await screen.findByText("There is already an invitation open for that address."),
    ).toBeTruthy();
  });

  it("names the last-owner rule exactly, rather than saying something went wrong", async () => {
    // A 409 here means the organisation would be left with nobody in charge.
    // "Try again" would be advice that cannot work.
    PATCH.mockResolvedValue({ error: { detail: "x" }, response: { status: 409 } });
    renderUi(panel());
    await screen.findByText("Rahul Verma");

    const select = screen.getAllByRole("combobox")[0];
    fireEvent.change(select, { target: { value: "member" } });

    expect(
      await screen.findByText(/only owner. Make somebody else an owner first/),
    ).toBeTruthy();
  });

  it("shows pending invitations with a way to withdraw them", async () => {
    world_(
      [member(), colleague],
      [
        {
          id: "i1",
          email: "waiting@apollo-care.example",
          role: "member",
          state: "pending",
          expires_at: "2026-09-29T09:00:00Z",
          created_at: "2026-09-22T09:00:00Z",
          invited_by: "Priya Sharma",
        },
      ],
    );
    renderUi(panel());

    expect(await screen.findByText("waiting@apollo-care.example")).toBeTruthy();
    expect(screen.getByText("Pending")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(DELETE).toHaveBeenCalledTimes(1));
    const [path] = DELETE.mock.calls[0] as [string];
    expect(path).toBe("/org/{org_slug}/invitations/{invitation_id}");
  });

  it("offers no revoke for an invitation already spent", async () => {
    world_(
      [member(), colleague],
      [
        {
          id: "i1",
          email: "joined@apollo-care.example",
          role: "member",
          state: "accepted",
          expires_at: "2026-09-29T09:00:00Z",
          created_at: "2026-09-22T09:00:00Z",
          invited_by: null,
        },
      ],
    );
    renderUi(panel());

    expect(await screen.findByText("Accepted")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Revoke" })).toBeNull();
  });
});
