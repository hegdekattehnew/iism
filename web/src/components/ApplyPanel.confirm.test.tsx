import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplyPanel } from "@/components/ApplyPanel";
import { personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a), PUT: vi.fn(), DELETE: vi.fn() },
}));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  GET.mockResolvedValue({ data: [], error: undefined, response: { status: 200 } });
  world.memberships = [personal()];
});

const open = () => {
  renderUi(<ApplyPanel jobSlug="cashier-bengaluru" organisation="Apply Co" />);
  fireEvent.click(screen.getByRole("button", { name: "Apply for this job" }));
  return screen.getByRole("group", { name: "Before you apply" });
};

/** Sprint 86, BL-19.16: the confirmation is laid out again; what it tells the person is the same. */
describe("ApplyPanel: the confirmation", () => {
  it("is one group named by its heading, with the disclosure, the note field and the two buttons", () => {
    const group = open();
    expect(within(group).getByRole("heading", { level: 2, name: "Before you apply" })).toBeTruthy();
    expect(within(group).getByText(/sends your name, mobile number and email to Apply Co, for this vacancy only/)).toBeTruthy();
    expect(within(group).getByText(/they stop seeing your contact details/)).toBeTruthy();
    expect(within(group).getByLabelText("Add a note (optional)")).toBeTruthy();
    expect(within(group).getByRole("button", { name: "Yes, apply" })).toBeTruthy();
    expect(within(group).getByRole("button", { name: "Cancel" })).toBeTruthy();
  });

  it("marks the disclosure with a shape, hidden from a screen reader (the words say it)", () => {
    const group = open();
    const mark = group.querySelector("[aria-hidden='true']") as HTMLElement;
    expect(mark.querySelector("svg")).toBeTruthy();
    expect(mark.className).toContain("bg-info-surface");
  });

  it("keeps the note's limit at the field, and is a 44 px control", () => {
    const group = open();
    const note = within(group).getByLabelText("Add a note (optional)");
    expect(note.getAttribute("maxlength")).toBe("1000");
    expect(note.className).toContain("min-h-11");
  });

  it("shows a refusal inside the confirmation, next to the buttons, and keeps what was typed", async () => {
    POST.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    const group = open();
    fireEvent.change(within(group).getByLabelText("Add a note (optional)"), { target: { value: "I have five years on a ward." } });
    fireEvent.click(within(group).getByRole("button", { name: "Yes, apply" }));
    const alert = await within(group).findByRole("alert");
    expect(alert.textContent).toBe("Something went wrong. Try again.");
    expect((within(group).getByLabelText("Add a note (optional)") as HTMLTextAreaElement).value).toBe("I have five years on a ward.");
    // said once: not again under the box
    expect(screen.getAllByText("Something went wrong. Try again.").length).toBe(1);
  });

  it("keeps the note when the step is closed and opened again", () => {
    const group = open();
    fireEvent.change(within(group).getByLabelText("Add a note (optional)"), { target: { value: "Keep me." } });
    fireEvent.click(within(group).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("group", { name: "Before you apply" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Apply for this job" }));
    expect((screen.getByLabelText("Add a note (optional)") as HTMLTextAreaElement).value).toBe("Keep me.");
  });

  it("sends the note, and clears it when the application is made", async () => {
    POST.mockResolvedValue({ data: { id: "a1", status: "applied", job: { slug: "cashier-bengaluru" } }, error: undefined, response: { status: 201 } });
    const group = open();
    fireEvent.change(within(group).getByLabelText("Add a note (optional)"), { target: { value: "  Hello.  " } });
    fireEvent.click(within(group).getByRole("button", { name: "Yes, apply" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0][0]).toBe("/me/applications");
    expect((POST.mock.calls[0][1] as { body: { message: string } }).body.message).toBe("Hello.");
    await waitFor(() => expect(screen.queryByRole("group", { name: "Before you apply" })).toBeNull());
  });

  it("starts the next application's note empty: a success clears what was sent", async () => {
    let made = false;
    GET.mockImplementation(async (path: string) =>
      path === "/me/applications"
        ? {
            data: made ? [{ id: "a1", status: "withdrawn", job: { slug: "cashier-bengaluru" } }] : [],
            error: undefined,
            response: { status: 200 },
          }
        : { data: [], error: undefined, response: { status: 200 } },
    );
    POST.mockImplementation(async () => {
      made = true;
      return { data: { id: "a1", status: "applied", job: { slug: "cashier-bengaluru" } }, error: undefined, response: { status: 201 } };
    });
    const group = open();
    fireEvent.change(within(group).getByLabelText("Add a note (optional)"), { target: { value: "First note." } });
    fireEvent.click(within(group).getByRole("button", { name: "Yes, apply" }));
    await waitFor(() => expect(screen.queryByRole("group", { name: "Before you apply" })).toBeNull());
    // the application has since been withdrawn, so the button is offered again
    fireEvent.click(await screen.findByRole("button", { name: "Apply for this job" }));
    expect((screen.getByLabelText("Add a note (optional)") as HTMLTextAreaElement).value).toBe("");
  });

  it("stacks the buttons on a phone, the primary first in reading order from sm up", () => {
    const group = open();
    const yes = within(group).getByRole("button", { name: "Yes, apply" });
    expect(yes.className).toContain("w-full");
    expect((yes.parentElement as HTMLElement).className).toContain("flex-col");
    expect((yes.parentElement as HTMLElement).className).toContain("sm:flex-row-reverse");
  });

  it("shows a refusal outside the confirmation when it is not open (a withdrawal that failed)", async () => {
    GET.mockImplementation(async (path: string) =>
      path === "/me/applications"
        ? { data: [{ id: "a1", status: "applied", job: { slug: "cashier-bengaluru" } }], error: undefined, response: { status: 200 } }
        : { data: [], error: undefined, response: { status: 200 } },
    );
    POST.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    renderUi(<ApplyPanel jobSlug="cashier-bengaluru" organisation="Apply Co" />);
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw" }));
    expect((await screen.findByText("Something went wrong. Try again.")).closest("[role='group']")).toBeNull();
  });
});
