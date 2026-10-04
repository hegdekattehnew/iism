import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RoleAliasEditor } from "@/components/ops/RoleAliasEditor";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
  },
}));

/**
 * The screen a labour-market reviewer uses to fix role search (Sprint 47). What matters is
 * that the checks the server runs are *heard before* the button is pressed, that the target
 * is picked rather than typed, and that a support-tier operator is told, not shown a broken panel.
 */

const gda = {
  slug: "gda",
  job_role: "General Duty Assistant",
  nsqf_level: 4,
  sector_name: "Healthcare",
};
const alias = (over: Record<string, unknown> = {}) => ({
  id: "a1",
  surface_form: "ward boy",
  job_role: "General Duty Assistant",
  source: "seed",
  created_at: "2026-10-04T09:00:00Z",
  ...over,
});
const okCheck = {
  ok: true,
  surface_form: "ayah",
  target: {
    job_role: "General Duty Assistant",
    slug: "gda",
    qp_code: "HSS/Q5101",
    nsqf_level: 4,
    standards_count: 7,
    sector_name: "Healthcare",
  },
  problems: [],
  warnings: [],
};

const TWO = [alias(), alias({ id: "a2", surface_form: "ayah", source: "operator" })];

function world({
  aliases = TWO,
  total = aliases.length,
  history = [] as unknown[],
  listStatus = 200,
}: { aliases?: unknown[]; total?: number; history?: unknown[]; listStatus?: number } = {}) {
  GET.mockImplementation((path: string) => {
    if (path === "/ops/role-aliases") {
      return Promise.resolve(
        listStatus === 200
          ? { data: { items: aliases, total }, error: undefined, response: { status: 200 } }
          : { data: undefined, error: { detail: "Forbidden" }, response: { status: listStatus } },
      );
    }
    if (path === "/ops/role-aliases/history") {
      return Promise.resolve({ data: history, error: undefined, response: { status: 200 } });
    }
    if (path === "/roles/search") return Promise.resolve({ data: [gda] });
    return Promise.resolve({ data: undefined, error: { detail: "nope" }, response: { status: 404 } });
  });
}

const pickTarget = async () => {
  fireEvent.change(screen.getByPlaceholderText("Search the national roles"), {
    target: { value: "duty" },
  });
  fireEvent.click(await screen.findByRole("button", { name: /General Duty Assistant/ }));
};
const typeTerm = (value: string) =>
  fireEvent.change(screen.getByPlaceholderText(/e\.g\. ward boy/), { target: { value } });

beforeEach(() => {
  resetWorld();
  [GET, POST].forEach((m) => m.mockReset());
  world();
  POST.mockImplementation((path: string) => {
    if (path === "/ops/role-aliases/check") {
      return Promise.resolve({ data: okCheck, error: undefined, response: { status: 200 } });
    }
    return Promise.resolve({
      data: alias({ id: "new", surface_form: "ayah", source: "operator" }),
      error: undefined,
      response: { status: 201 },
    });
  });
});

describe("RoleAliasEditor — who sees it", () => {
  it("tells a support-tier operator it is not theirs, rather than showing a broken panel", async () => {
    world({ listStatus: 403 });
    renderUi(<RoleAliasEditor />);
    expect(await screen.findByText("Only an admin-tier operator can edit role aliases.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add alias" })).toBeNull();
  });
});

describe("RoleAliasEditor — the list", () => {
  it("shows each alias with where it came from, and the total", async () => {
    renderUi(<RoleAliasEditor />);
    expect(await screen.findByText("ward boy")).toBeTruthy();
    expect(screen.getByText("Starter list")).toBeTruthy();
    expect(screen.getByText("Added here")).toBeTruthy();
    expect(screen.getByText("Showing 2 of 2")).toBeTruthy();
  });

  it("says how many of the whole there are when the list is cut", async () => {
    world({ total: 114 });
    renderUi(<RoleAliasEditor />);
    expect(await screen.findByText("Showing 2 of 114")).toBeTruthy();
  });

  it("retires an alias only after asking", async () => {
    const confirm = vi.spyOn(window, "confirm");
    renderUi(<RoleAliasEditor />);
    await screen.findByText("ward boy");

    confirm.mockReturnValueOnce(false);
    fireEvent.click(screen.getAllByRole("button", { name: "Retire" })[0]);
    expect(POST).not.toHaveBeenCalled();

    confirm.mockReturnValueOnce(true);
    fireEvent.click(screen.getAllByRole("button", { name: "Retire" })[0]);
    await waitFor(() =>
      expect(POST).toHaveBeenCalledWith("/ops/role-aliases/{alias_id}/retire", {
        params: { path: { alias_id: "a1" } },
        body: { note: undefined },
      }),
    );
    confirm.mockRestore();
  });

  it("shows the recent changes", async () => {
    world({
      history: [
        {
          action: "added",
          surface_form: "ayah",
          job_role: "General Duty Assistant",
          note: "heard on the ward",
          created_at: "2026-10-04T09:00:00Z",
        },
      ],
    });
    renderUi(<RoleAliasEditor />);
    expect(await screen.findByText(/Added "ayah" → General Duty Assistant/)).toBeTruthy();
    expect(screen.getByText(/heard on the ward/)).toBeTruthy();
  });
});

describe("RoleAliasEditor — adding", () => {
  it("cannot be pressed until a role is chosen and the check passes", async () => {
    renderUi(<RoleAliasEditor />);
    const add = (await screen.findByRole("button", { name: "Add alias" })) as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    typeTerm("ayah");
    expect(add.disabled).toBe(true); // a term alone is not enough
    await pickTarget();
    await screen.findByText(/Typing this will find General Duty Assistant/);
    expect(add.disabled).toBe(false);
  });

  it("checks the pair as it is typed, and shows what it would find", async () => {
    renderUi(<RoleAliasEditor />);
    await screen.findByText("ward boy");
    typeTerm("ayah");
    await pickTarget();
    await waitFor(() =>
      expect(POST).toHaveBeenCalledWith("/ops/role-aliases/check", {
        body: { surface_form: "ayah", job_role: "General Duty Assistant" },
      }),
    );
    expect(await screen.findByText(/HSS\/Q5101 · 7 standards/)).toBeTruthy();
  });

  it("shows the reason an alias is wrong and keeps the button off", async () => {
    POST.mockImplementation(() =>
      Promise.resolve({
        data: {
          ...okCheck,
          ok: false,
          problems: ["'General Duty Assistant' resolves to a disability-track pack (PWD/X)."],
        },
        error: undefined,
        response: { status: 200 },
      }),
    );
    renderUi(<RoleAliasEditor />);
    await screen.findByText("ward boy");
    typeTerm("ayah");
    await pickTarget();
    expect(await screen.findByText(/disability-track pack/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Add alias" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("shows an ambiguity warning and still lets the operator add", async () => {
    POST.mockImplementation(() =>
      Promise.resolve({
        data: { ...okCheck, warnings: ["Typing 'wel' also reaches welder."] },
        error: undefined,
        response: { status: 200 },
      }),
    );
    renderUi(<RoleAliasEditor />);
    await screen.findByText("ward boy");
    typeTerm("welfare aide");
    await pickTarget();
    expect(await screen.findByText(/also reaches welder/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Add alias" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("sends the term, the role the corpus spells and the note, then confirms and clears", async () => {
    renderUi(<RoleAliasEditor />);
    await screen.findByText("ward boy");
    typeTerm("ayah");
    await pickTarget();
    fireEvent.change(screen.getByPlaceholderText(/what it is called on the ward/), {
      target: { value: " heard on a ward " },
    });
    await screen.findByText(/Typing this will find/);
    fireEvent.click(screen.getByRole("button", { name: "Add alias" }));

    await waitFor(() =>
      expect(POST).toHaveBeenCalledWith("/ops/role-aliases", {
        body: { surface_form: "ayah", job_role: "General Duty Assistant", note: "heard on a ward" },
      }),
    );
    expect(await screen.findByText('Added "ayah".')).toBeTruthy();
    expect((screen.getByPlaceholderText(/e\.g\. ward boy/) as HTMLInputElement).value).toBe("");
  });

  it("shows the server's own sentence when adding is refused", async () => {
    POST.mockImplementation((path: string) =>
      path === "/ops/role-aliases/check"
        ? Promise.resolve({ data: okCheck, error: undefined, response: { status: 200 } })
        : Promise.resolve({
            data: undefined,
            error: { detail: "'ayah' already points at 'Welder'. Retire it first to change it." },
            response: { status: 409 },
          }),
    );
    renderUi(<RoleAliasEditor />);
    await screen.findByText("ward boy");
    typeTerm("ayah");
    await pickTarget();
    await screen.findByText(/Typing this will find/);
    fireEvent.click(screen.getByRole("button", { name: "Add alias" }));
    expect(await screen.findByText(/already points at 'Welder'/)).toBeTruthy();
  });

  it("falls back to a generic line for a failure that carried nothing", async () => {
    POST.mockImplementation((path: string) =>
      path === "/ops/role-aliases/check"
        ? Promise.resolve({ data: okCheck, error: undefined, response: { status: 200 } })
        : Promise.resolve({ data: undefined, error: { oops: true }, response: { status: 500 } }),
    );
    renderUi(<RoleAliasEditor />);
    await screen.findByText("ward boy");
    typeTerm("ayah");
    await pickTarget();
    await screen.findByText(/Typing this will find/);
    fireEvent.click(screen.getByRole("button", { name: "Add alias" }));
    expect(await screen.findByText("The alias could not be added. Try again.")).toBeTruthy();
  });
});
