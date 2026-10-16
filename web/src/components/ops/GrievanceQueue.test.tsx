import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GrievanceQueue } from "@/components/ops/GrievanceQueue";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

const ITEM = {
  id: "11111111-1111-1111-1111-111111111111",
  reference: "GRV-ABC234",
  kind: "grievance",
  status: "open",
  body: "My employer shared my number outside the vacancy.",
  reply_to: null,
  account: { phone: "+9198*****999", email: "pr****@example.com" },
  created_at: "2026-10-01T08:00:00Z",
  acknowledged_at: null,
  resolved_at: null,
  resolution_note: null,
  overdue_acknowledge: false,
  overdue_resolve: false,
};

function queue(items: unknown[], counts = { open: items.length, overdue: 0 }) {
  GET.mockResolvedValue({
    data: { items, ...counts },
    error: undefined,
    response: { status: 200 },
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  queue([ITEM]);
  POST.mockResolvedValue({
    data: { ...ITEM, status: "acknowledged" },
    error: undefined,
    response: { status: 200 },
  });
});

describe("the grievance queue", () => {
  it("shows what was sent and the account only masked", async () => {
    renderUi(<GrievanceQueue />);
    expect(await screen.findByText("GRV-ABC234")).toBeTruthy();
    expect(screen.getByText(/shared my number/)).toBeTruthy();
    expect(screen.getByText("+9198*****999 · pr****@example.com")).toBeTruthy();
  });

  it("shows a stranger's reply address as given", async () => {
    queue([{ ...ITEM, account: null, reply_to: "ravi@example.org" }]);
    renderUi(<GrievanceQueue />);
    expect(await screen.findByText("ravi@example.org")).toBeTruthy();
  });

  it("flags a message that is late against what the page promises", async () => {
    queue([{ ...ITEM, overdue_acknowledge: true }], { open: 1, overdue: 1 });
    renderUi(<GrievanceQueue />);
    expect(await screen.findByText("Not acknowledged in time")).toBeTruthy();
    expect(screen.getByText("1 waiting · 1 late")).toBeTruthy();
  });

  it("says the queue is answered rather than rendering nothing", async () => {
    queue([]);
    renderUi(<GrievanceQueue />);
    expect(
      await screen.findByText(/Nobody is waiting on an answer/),
    ).toBeTruthy();
  });

  it("starts on everything, so a message acknowledged but not resolved stays in sight", async () => {
    renderUi(<GrievanceQueue />);
    await screen.findByText("GRV-ABC234");
    expect(GET.mock.calls[0][1].params.query).toEqual({});
    expect((screen.getByLabelText("Show") as HTMLSelectElement).value).toBe("all");
  });

  it("acknowledges without a note", async () => {
    renderUi(<GrievanceQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Acknowledge" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][0]).toBe(
      "/ops/grievances/{grievance_id}/acknowledge",
    );
  });

  it("will not resolve or dismiss without a real note, and sends the note it was given", async () => {
    renderUi(<GrievanceQueue />);
    const resolve = (await screen.findByRole("button", {
      name: "Resolve",
    })) as HTMLButtonElement;
    const dismiss = screen.getByRole("button", {
      name: "Dismiss",
    }) as HTMLButtonElement;
    expect(resolve.disabled && dismiss.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText(/Note/), {
      target: { value: "short" },
    });
    expect(resolve.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText(/Note/), {
      target: { value: "Wrote back and told the employer to stop." },
    });
    expect(resolve.disabled).toBe(false);
    fireEvent.click(resolve);
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][0]).toBe(
      "/ops/grievances/{grievance_id}/resolve",
    );
    expect(POST.mock.calls[0][1].body.note).toBe(
      "Wrote back and told the employer to stop.",
    );
  });

  it("says what the server said when a decision is refused", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "That has already been closed." },
      response: { status: 409 },
    });
    renderUi(<GrievanceQueue />);
    fireEvent.click(await screen.findByRole("button", { name: "Acknowledge" }));
    expect(
      await screen.findByText("That has already been closed."),
    ).toBeTruthy();
  });

  it("offers no decision on a closed message and shows the note it was closed with", async () => {
    queue([
      {
        ...ITEM,
        status: "resolved",
        acknowledged_at: "2026-10-01T09:00:00Z",
        resolved_at: "2026-10-03T09:00:00Z",
        resolution_note: "Employer removed the listing.",
      },
    ]);
    renderUi(<GrievanceQueue />);
    expect(
      await screen.findByText("Employer removed the listing."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Resolve" })).toBeNull();
  });

  it("says so when the queue cannot be read", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: {},
      response: { status: 500 },
    });
    renderUi(<GrievanceQueue />);
    expect(
      await screen.findByText("Could not load the messages."),
    ).toBeTruthy();
  });

  it("keeps its filter at the 44 px floor (Sprint 73)", async () => {
    const { container } = renderUi(<GrievanceQueue />);
    expect(container.querySelector("#grievance-filter")!.className).toMatch(/min-h-11/);
  });
});
