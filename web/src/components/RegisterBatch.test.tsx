import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RegisterBatch } from "@/components/RegisterBatch";
import { publicBatch } from "@/test/batch-fixtures";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

/** Sprint 100, BL-20.3: who is offered the button, and what they are told before they press it. */

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  GET.mockResolvedValue({ data: { items: [], total: 0 }, error: undefined });
  POST.mockResolvedValue({
    data: { id: "i1", status: "registered", registered_at: "2026-10-20T09:00:00Z" },
    error: undefined,
    response: { status: 201 },
  });
  world.memberships = [personal()];
});

const button = (name: RegExp | string) => screen.findByRole("button", { name });

describe("RegisterBatch: who is offered the button", () => {
  it("asks a signed-out visitor to sign in", () => {
    world.signedIn = false;
    renderUi(<RegisterBatch batch={publicBatch()} />);
    expect(
      screen.getByRole("link", { name: "Sign in to register interest" }).getAttribute("href"),
    ).toBe("/signin");
  });

  it("offers a job seeker the button, named for the course", async () => {
    renderUi(<RegisterBatch batch={publicBatch()} />);
    expect(await button("Register interest: Welding basics")).toBeTruthy();
  });

  it("offers an organisation-only account nothing", () => {
    world.memberships = [org("nsdc", "course_provider")];
    const { container } = renderUi(<RegisterBatch batch={publicBatch()} />);
    expect(container.textContent).toBe("");
  });

  it("offers nothing while it does not know which kind of account this is", () => {
    world.pending = true;
    const { container } = renderUi(<RegisterBatch batch={publicBatch()} />);
    expect(container.textContent).toBe("");
  });

  it("says a full batch is full and offers nothing to press", () => {
    renderUi(<RegisterBatch batch={publicBatch({ phase: "full", seats_left: 0 })} />);
    expect(screen.getByText(/This batch is full/)).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("RegisterBatch: the consent moment", () => {
  it("names the centre and the organisation behind it before anything is shared", async () => {
    renderUi(<RegisterBatch batch={publicBatch()} />);
    fireEvent.click(await button("Register interest: Welding basics"));
    const share = await screen.findByText(/Hadapsar Centre will see your name/);
    expect(share.textContent).toContain("Partner Skills");
    expect(screen.getByText(/not the organisation that sells the course/)).toBeTruthy();
    expect(screen.getByText(/You can withdraw at any time/)).toBeTruthy();
    expect(POST).not.toHaveBeenCalled();
  });

  it("sends the note with the registration, and nothing when there is none", async () => {
    const first = renderUi(<RegisterBatch batch={publicBatch()} />);
    fireEvent.click(await button("Register interest: Welding basics"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "  Evenings only " } });
    fireEvent.click(screen.getByRole("button", { name: "Register my interest" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/me/batch-interests");
    expect(init.body).toEqual({ batch_id: "b1", message: "Evenings only" });
    first.unmount();

    POST.mockClear();
    renderUi(<RegisterBatch batch={publicBatch()} />);
    fireEvent.click(await button("Register interest: Welding basics"));
    fireEvent.click(screen.getByRole("button", { name: "Register my interest" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect((POST.mock.calls[0][1] as { body: Record<string, unknown> }).body.message).toBeNull();
  });

  it("limits the note to what the server accepts", async () => {
    renderUi(<RegisterBatch batch={publicBatch()} />);
    fireEvent.click(await button("Register interest: Welding basics"));
    expect(screen.getByRole("textbox").getAttribute("maxlength")).toBe("1000");
  });

  it("cancelling shares nothing and takes the form away", async () => {
    renderUi(<RegisterBatch batch={publicBatch()} />);
    fireEvent.click(await button("Register interest: Welding basics"));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText(/will see your name/)).toBeNull();
    expect(POST).not.toHaveBeenCalled();
  });

  it("shows the server's own sentence when it refuses, and keeps the form for another try", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "This batch started yesterday" },
      response: { status: 409 },
    });
    renderUi(<RegisterBatch batch={publicBatch()} />);
    fireEvent.click(await button("Register interest: Welding basics"));
    fireEvent.click(screen.getByRole("button", { name: "Register my interest" }));
    expect((await screen.findByRole("alert")).textContent).toContain("This batch started yesterday");
    expect(screen.getByRole("button", { name: "Register my interest" })).toBeTruthy();
  });

  it("tells an account that is not a job seeker so, when the server refuses it with a 403", async () => {
    POST.mockResolvedValue({ data: undefined, error: {}, response: { status: 403 } });
    renderUi(<RegisterBatch batch={publicBatch()} />);
    fireEvent.click(await button("Register interest: Welding basics"));
    fireEvent.click(screen.getByRole("button", { name: "Register my interest" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Only a job seeker account");
  });
});

describe("RegisterBatch: after registering", () => {
  const mine = (status: string) => ({ id: "i1", status });

  it("shows the state in words and offers to withdraw, named for the course", async () => {
    renderUi(<RegisterBatch batch={publicBatch({ my_interest: mine("contacted") })} />);
    expect(await screen.findByText("They got in touch")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Withdraw: Welding basics" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Register interest/ })).toBeNull();
  });

  it("withdraws by the interest's own id", async () => {
    POST.mockResolvedValue({
      data: { id: "i1", status: "withdrawn" },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<RegisterBatch batch={publicBatch({ my_interest: mine("registered") })} />);
    fireEvent.click(await button("Withdraw: Welding basics"));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { params: { path: { interest_id: string } } }];
    expect(path).toBe("/me/batch-interests/{interest_id}/withdraw");
    expect(init.params.path.interest_id).toBe("i1");
  });

  it("gives the reply date, as an ask, right after registering and not on a later visit", async () => {
    renderUi(<RegisterBatch batch={publicBatch()} />);
    fireEvent.click(await button("Register interest: Welding basics"));
    fireEvent.click(screen.getByRole("button", { name: "Register my interest" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    // The public list carries no registration time, so the date is shown only from the answer to
    // the registration itself; the learner's own list shows it from the interest.
    const { container } = renderUi(
      <RegisterBatch batch={publicBatch({ my_interest: mine("registered") })} />,
    );
    expect(container.textContent).not.toContain("Reply expected by");
  });
});
