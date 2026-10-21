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


  // Every notice used to be worded as an application status change, so a job
  // alert read "Acme moved your application for Cashier to: Applied" about a
  // vacancy nobody had applied to.
  describe("wording follows the template", () => {
    it("words a job alert as a vacancy, not as an application update", async () => {
      GET.mockResolvedValue({
        data: [
          notice({
            template: "job_alert",
            payload: { vacancy: "Cashier", organisation: "Acme", path: "/jobs/cashier-bengaluru" },
          }),
        ],
        error: undefined,
      });
      renderUi(<Notices />);

      expect(await screen.findByText(/Acme published Cashier/)).toBeTruthy();
      expect(screen.queryByText(/moved your application/)).toBeNull();
      expect(screen.getByRole("link", { name: "Open" }).getAttribute("href")).toBe(
        "/jobs/cashier-bengaluru",
      );
    });

    it("words a closed vacancy as closed", async () => {
      GET.mockResolvedValue({
        data: [notice({ template: "vacancy_closed", payload: { vacancy: "Cashier" } })],
        error: undefined,
      });
      renderUi(<Notices />);

      expect(await screen.findByText("Cashier is no longer taking applications.")).toBeTruthy();
    });

    it("words a provider's update on a course interest", async () => {
      GET.mockResolvedValue({
        data: [
          notice({
            template: "course_interest_status_changed",
            payload: {
              course: "Phlebotomy Refresher",
              organisation: "SkillBridge",
              status: "enrolled",
              path: "/interests",
            },
          }),
        ],
        error: undefined,
      });
      renderUi(<Notices />);

      expect(
        await screen.findByText(
          "SkillBridge marked your interest in Phlebotomy Refresher as: Enrolled.",
        ),
      ).toBeTruthy();
      expect(screen.queryByText(/moved your application/)).toBeNull();
      expect(screen.getByRole("link", { name: "Open" }).getAttribute("href")).toBe("/interests");
    });

    it("words a sponsorship offer, naming the organisation, the standard and the course", async () => {
      GET.mockResolvedValue({
        data: [
          notice({
            template: "sponsor_offer",
            payload: {
              vacancy: "General Duty Assistant",
              organisation: "Apollo Care",
              standard: "Follow infection control policies",
              course: "Infection Control in Hospitals",
              path: "/jobs/general-duty-assistant-chennai",
            },
          }),
        ],
        error: undefined,
      });
      renderUi(<Notices />);

      expect(
        await screen.findByText(
          "Apollo Care would sponsor you to close a gap for General Duty Assistant: take Infection Control in Hospitals, which teaches “Follow infection control policies”.",
        ),
      ).toBeTruthy();
      // It used to fall through to this, which says nothing.
      expect(screen.queryByText("You have an update.")).toBeNull();
      expect(screen.getByRole("link", { name: "Open" }).getAttribute("href")).toBe(
        "/jobs/general-duty-assistant-chennai",
      );
    });

    it("says something neutral for a template it does not know", async () => {
      GET.mockResolvedValue({
        data: [notice({ template: "something_new", payload: {} })],
        error: undefined,
      });
      renderUi(<Notices />);

      expect(await screen.findByText("You have an update.")).toBeTruthy();
      expect(screen.queryByText(/moved your application/)).toBeNull();
    });

    it("never links a notice off-site", async () => {
      GET.mockResolvedValue({
        data: [
          notice({ template: "job_alert", payload: { vacancy: "Cashier", path: "https://evil.example/x" } }),
        ],
        error: undefined,
      });
      renderUi(<Notices />);

      await screen.findByText(/Cashier/);
      expect(screen.queryByRole("link", { name: "Open" })).toBeNull();
    });
  });

  it("words a grievance update by where the message stands, and links to the page it lives on", async () => {
    GET.mockResolvedValue({
      data: [
        notice({
          template: "grievance_update",
          payload: { reference: "GRV-ABC234", status: "resolved" },
        }),
      ],
      error: undefined,
    });
    renderUi(<Notices />);
    expect(
      await screen.findByText("Your message GRV-ABC234 is now: resolved."),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open" }).getAttribute("href")).toBe("/grievance");
  });

  it("marks a notice with its kind's shape and makes its link 44 px (Sprint 87)", async () => {
    GET.mockResolvedValue({
      data: [
        {
          id: "n1",
          template: "vacancy_closed",
          payload: { vacancy: "Cashier", path: "/jobs/cashier" },
          created_at: "2026-10-01T00:00:00Z",
          read_at: null,
        },
      ],
      error: undefined,
      response: { status: 200 },
    });
    const { container } = renderUi(<Notices />);
    const link = await screen.findByRole("link", { name: "Open" });
    expect(link.className).toContain("min-h-11");
    const tile = container.querySelector("li > [aria-hidden='true']") as HTMLElement;
    expect(tile.querySelector("svg")).toBeTruthy();
    expect(tile.className).toContain("bg-accent-soft");
  });
});
