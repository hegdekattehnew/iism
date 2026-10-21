import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NotificationsPage } from "@/components/NotificationsPage";
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

const notice = (i: number, over: Record<string, unknown> = {}) => ({
  id: `00000000-0000-0000-0000-${String(i).padStart(12, "0")}`,
  template: "vacancy_closed",
  payload: { vacancy: `Cashier ${i}`, path: "/applications" },
  created_at: new Date(Date.UTC(2026, 9, 1, 0, 0, 100 - i)).toISOString(),
  read_at: null,
  ...over,
});

const page = (items: unknown[]) => ({
  data: items,
  error: undefined,
  response: { status: 200 },
});

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  POST.mockResolvedValue({
    data: undefined,
    error: undefined,
    response: { status: 204 },
  });
});

describe("the notification page", () => {
  it("lists notices in words, says which are new, and points each at where it belongs", async () => {
    GET.mockResolvedValue(
      page([
        notice(1),
        notice(2, { read_at: "2026-10-02T00:00:00Z" }),
        notice(3, {
          template: "grievance_update",
          payload: { reference: "GRV-ABC234", status: "resolved" },
        }),
      ]),
    );
    renderUi(<NotificationsPage />);
    expect(
      await screen.findByText("Cashier 1 is no longer taking applications."),
    ).toBeTruthy();
    expect(
      screen.getByText("Your message GRV-ABC234 is now: resolved."),
    ).toBeTruthy();
    expect(screen.getAllByText("New")).toHaveLength(2);
    expect(screen.getByText("2 unread")).toBeTruthy();
    const hrefs = screen
      .getAllByRole("link", { name: "Open" })
      .map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["/applications", "/applications", "/grievance"]);
  });

  it("words a status change that carries a message, without the message", async () => {
    GET.mockResolvedValue(
      page([
        notice(1, {
          template: "application_status_message",
          payload: {
            vacancy: "Cashier",
            organisation: "Acme",
            status: "shortlisted",
            has_message: true,
          },
        }),
      ]),
    );
    renderUi(<NotificationsPage />);
    expect(
      await screen.findByText(
        /Acme moved your application for Cashier to: Shortlisted, and left you a message/,
      ),
    ).toBeTruthy();
  });

  it("marks each notice with the shape of its kind, bright while new", async () => {
    GET.mockResolvedValue(
      page([notice(1), notice(2, { read_at: "2026-10-02T00:00:00Z", template: "grievance_update", payload: { reference: "GRV-ABC234", status: "resolved" } })]),
    );
    const { container } = renderUi(<NotificationsPage />);
    await screen.findByText("Cashier 1 is no longer taking applications.");
    const tiles = [...container.querySelectorAll("li > [aria-hidden='true']")] as HTMLElement[];
    expect(tiles.length).toBe(2);
    for (const t of tiles) expect(t.querySelector("svg")).toBeTruthy();
    expect(tiles[0].className).toContain("bg-accent-soft");
    expect(tiles[1].className).toContain("bg-surface-muted");
  });

  it("makes both actions on a notice 44 px", async () => {
    GET.mockResolvedValue(page([notice(1)]));
    renderUi(<NotificationsPage />);
    expect((await screen.findByRole("link", { name: "Open" })).className).toContain("min-h-11");
    expect(screen.getByRole("button", { name: "Mark as read" }).className).toContain("min-h-11");
  });

  it("reads one notice, and reads them all", async () => {
    GET.mockResolvedValue(page([notice(1), notice(2)]));
    renderUi(<NotificationsPage />);
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "Mark as read" }))[0],
    );
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0][0]).toBe(
      "/me/notifications/{notification_id}/read",
    );
    expect(POST.mock.calls[0][1].params.path.notification_id).toBe(
      notice(1).id,
    );

    fireEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(2));
    expect(POST.mock.calls[1][0]).toBe("/me/notifications/read");
  });

  it("offers no 'mark all' when everything is read", async () => {
    GET.mockResolvedValue(
      page([notice(1, { read_at: "2026-10-02T00:00:00Z" })]),
    );
    renderUi(<NotificationsPage />);
    expect(await screen.findByText("Everything read")).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Mark all as read" }),
    ).toBeNull();
  });

  it("goes past the first page with the last notice's time and id as the cursor", async () => {
    const first = Array.from({ length: 30 }, (_, i) => notice(i + 1));
    const second = [notice(31), notice(32)];
    GET.mockResolvedValueOnce(page(first)).mockResolvedValueOnce(page(second));
    renderUi(<NotificationsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Show older updates" }),
    );
    expect(
      await screen.findByText("Cashier 32 is no longer taking applications."),
    ).toBeTruthy();
    const second_call = GET.mock.calls[1][1].params.query;
    expect(second_call).toEqual({
      limit: 30,
      before: first[29].created_at,
      before_id: first[29].id,
    });
    expect(
      screen.queryByRole("button", { name: "Show older updates" }),
    ).toBeNull();
  });

  it("says plainly when there is nothing, and when it cannot be loaded", async () => {
    GET.mockResolvedValue(page([]));
    const { unmount } = renderUi(<NotificationsPage />);
    expect(await screen.findByText(/Nothing yet/)).toBeTruthy();
    unmount();
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "Down" },
      response: { status: 500 },
    });
    renderUi(<NotificationsPage />);
    expect(await screen.findByText("Down")).toBeTruthy();
  });

  it("asks a signed-out visitor to sign in and requests nothing", () => {
    world.signedIn = false;
    renderUi(<NotificationsPage />);
    expect(screen.getByText("Sign in to see your updates.")).toBeTruthy();
    expect(GET).not.toHaveBeenCalled();
  });
});
