import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Notices } from "@/components/Notices";
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

/**
 * The in-app channel, and the one this product actually reaches candidates
 * on: 39 of 40 seeded candidates are phone-only and SMS waits on DLT.
 *
 * `markRead` did not read `error` **at all**. openapi-fetch resolves rather
 * than throws on a non-2xx, so a 401 or a 500 ran `onSuccess`, the query
 * refetched, the notices came back still unread, and the button did nothing
 * for ever with nothing anywhere saying why.
 */

const notice = (over: Record<string, unknown> = {}) => ({
  id: "n1",
  read_at: null,
  created_at: new Date().toISOString(),
  template: "application_status_changed",
  payload: { vacancy: "Cashier", organisation: "Acme", status: "shortlisted" },
  ...over,
});

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  GET.mockResolvedValue({ data: [notice()], error: undefined });
  POST.mockResolvedValue({ data: undefined, error: undefined, response: { status: 204 } });
});

describe("Notices", () => {
  it("lists what is unread", async () => {
    renderUi(<Notices />);
    expect(await screen.findByText(/Cashier/)).toBeTruthy();
  });

  it("says so when marking read was refused, instead of appearing to work", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "Not authenticated" },
      response: { status: 401 },
    });
    renderUi(<Notices />);
    fireEvent.click(await screen.findByRole("button", { name: "Mark as read" }));

    expect(await screen.findByText("Not authenticated")).toBeTruthy();
  });

  it("falls back to its own line when the refusal carried nothing", async () => {
    POST.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    renderUi(<Notices />);
    fireEvent.click(await screen.findByRole("button", { name: "Mark as read" }));

    expect(await screen.findByText(/Could not mark these as read/)).toBeTruthy();
  });

  it("stays quiet when it worked", async () => {
    renderUi(<Notices />);
    fireEvent.click(await screen.findByRole("button", { name: "Mark as read" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(screen.queryByText(/Could not mark these as read/)).toBeNull();
  });
});
