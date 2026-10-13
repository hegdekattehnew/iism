import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReportQueue } from "@/components/ops/ReportQueue";
import { renderUi, resetWorld, world } from "@/test/harness";

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

const LISTING = {
  target_type: "job",
  target_id: "11111111-1111-1111-1111-111111111111",
  slug: "ward-assistant",
  title: "Ward assistant",
  organisation: { slug: "acme", name: "Acme Care" },
  status: "published",
  open_reports: 2,
  reasons: { asks_for_money: 1, fake_or_misleading: 1 },
  oldest: "2026-10-01T09:00:00Z",
  reports: [
    {
      reason: "asks_for_money",
      detail: "They asked for a deposit.",
      reporter: { phone: "+9198*****999", email: null },
      created_at: "2026-10-01T09:00:00Z",
    },
    {
      reason: "fake_or_misleading",
      detail: null,
      reporter: { phone: null, email: "pr****@example.com" },
      created_at: "2026-10-02T09:00:00Z",
    },
  ],
  taken_down_at: null,
  takedown_reason: null,
};

const queue = (items: unknown[]) =>
  GET.mockResolvedValue({
    data: { items, open_listings: items.length, taken_down: 0 },
    error: undefined,
    response: { status: 200 },
  });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  queue([LISTING]);
  POST.mockResolvedValue({
    data: {
      target_type: "job",
      target_id: LISTING.target_id,
      reports_closed: 2,
      taken_down: true,
    },
    error: undefined,
    response: { status: 200 },
  });
});

describe("the report queue", () => {
  it("shows a listing once, with who said what, the reporters masked", async () => {
    renderUi(<ReportQueue />);
    expect(await screen.findByText("Ward assistant")).toBeTruthy();
    expect(screen.getByText("Acme Care")).toBeTruthy();
    expect(screen.getByText("2 reports")).toBeTruthy();
    expect(screen.getByText("They asked for a deposit.")).toBeTruthy();
    expect(screen.getByText(/\+9198\*{5}999/)).toBeTruthy();
    expect(screen.getByText(/pr\*{4}@example\.com/)).toBeTruthy();
  });

  it("says the queue is answered rather than rendering nothing", async () => {
    queue([]);
    renderUi(<ReportQueue />);
    expect(
      await screen.findByText(/Nobody is waiting on a decision/),
    ).toBeTruthy();
  });

  it("says so when it cannot be read", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: {},
      response: { status: 500 },
    });
    renderUi(<ReportQueue />);
    expect(await screen.findByText("Could not load the reports.")).toBeTruthy();
  });

  it("will not dismiss or take down without a real note, then sends it", async () => {
    renderUi(<ReportQueue />);
    const dismiss = (await screen.findByRole("button", {
      name: "Dismiss reports",
    })) as HTMLButtonElement;
    const takedown = screen.getByRole("button", {
      name: "Take it down",
    }) as HTMLButtonElement;
    expect(dismiss.disabled && takedown.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText(/Note/), {
      target: { value: "short" },
    });
    expect(takedown.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Note/), {
      target: {
        value: "It asked applicants to pay a fee before an interview.",
      },
    });
    fireEvent.click(takedown);
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][0]).toBe(
      "/ops/listings/{target_type}/{target_id}/takedown",
    );
    expect(POST.mock.calls[0][1].body).toEqual({
      reason: "It asked applicants to pay a fee before an interview.",
    });
  });

  it("dismisses through its own endpoint", async () => {
    renderUi(<ReportQueue />);
    fireEvent.change(await screen.findByLabelText(/Note/), {
      target: { value: "Checked: the fee is refundable and stated." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Dismiss reports" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][0]).toBe(
      "/ops/reports/{target_type}/{target_id}/dismiss",
    );
  });

  it("does not offer a support operator the takedown, and says what a removal reason is for to an admin", async () => {
    world.staffTier = "support";
    const { unmount } = renderUi(<ReportQueue />);
    expect(
      await screen.findByRole("button", { name: "Dismiss reports" }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Take it down" })).toBeNull();
    expect(screen.queryByText(/emailed to the organisation/)).toBeNull();
    unmount();

    world.staffTier = "admin";
    renderUi(<ReportQueue />);
    expect(await screen.findByText(/emailed to the organisation/)).toBeTruthy();
  });

  it("says what the server said when a decision is refused", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "This listing is already taken down" },
      response: { status: 409 },
    });
    renderUi(<ReportQueue />);
    fireEvent.change(await screen.findByLabelText(/Note/), {
      target: {
        value: "It asked applicants to pay a fee before an interview.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Take it down" }));
    expect(
      await screen.findByText("This listing is already taken down"),
    ).toBeTruthy();
  });

  it("lists what has been removed, with the reason, and lets an admin restore it", async () => {
    GET.mockResolvedValue({
      data: {
        items: [
          {
            ...LISTING,
            open_reports: 0,
            reasons: {},
            reports: [],
            taken_down_at: "2026-10-05T09:00:00Z",
            takedown_reason: "It asked applicants to pay a fee.",
          },
        ],
        open_listings: 0,
        taken_down: 1,
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<ReportQueue />);
    fireEvent.change(await screen.findByLabelText("Listings"), {
      target: { value: "taken_down" },
    });
    expect(
      await screen.findByText("It asked applicants to pay a fee."),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Restore/ }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][0]).toBe(
      "/ops/listings/{target_type}/{target_id}/restore",
    );
  });
});
