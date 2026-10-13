import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReportListing } from "@/components/ReportListing";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: vi.fn(),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

/**
 * Reporting a listing (Sprint 59). What varies is who is signed in, and what the server answers:
 * a report is accountable, so a stranger is sent to sign in, and the two refusals a person can act
 * on ("you manage this listing", "you have already reported it") are shown in the server's words.
 */

const ok = () =>
  POST.mockResolvedValue({
    data: { received: true },
    error: undefined,
    response: { status: 201, headers: new Headers() },
  });
const refuse = (status: number, detail: string) =>
  POST.mockResolvedValue({
    data: undefined,
    error: { detail },
    response: { status, headers: new Headers() },
  });

const open = () =>
  fireEvent.click(screen.getByRole("button", { name: /Report this/ }));

beforeEach(() => {
  resetWorld();
  POST.mockReset();
  ok();
});

describe("reporting a listing", () => {
  it("sends a signed-out visitor to sign in rather than offer a form that cannot work", () => {
    world.signedIn = false;
    renderUi(<ReportListing kind="job" slug="ward-assistant" />);
    expect(screen.queryByRole("button", { name: /Report this/ })).toBeNull();
    expect(
      screen.getByRole("link", { name: "Sign in" }).getAttribute("href"),
    ).toBe("/signin");
  });

  it("names what is being reported, per kind", () => {
    const { unmount } = renderUi(<ReportListing kind="job" slug="a" />);
    expect(
      screen.getByRole("button", { name: "Report this vacancy" }),
    ).toBeTruthy();
    unmount();
    renderUi(<ReportListing kind="course" slug="a" />);
    expect(
      screen.getByRole("button", { name: "Report this course" }),
    ).toBeTruthy();
  });

  it("sends the reason and the words to the right endpoint, and says only that it arrived", async () => {
    renderUi(<ReportListing kind="job" slug="ward-assistant" />);
    open();
    fireEvent.change(screen.getByLabelText("What is wrong?"), {
      target: { value: "asks_for_money" },
    });
    fireEvent.change(screen.getByLabelText(/Anything else/), {
      target: { value: "  Asked for a deposit.  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));

    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][0]).toBe("/jobs/{slug}/report");
    expect(POST.mock.calls[0][1].params.path.slug).toBe("ward-assistant");
    expect(POST.mock.calls[0][1].body).toEqual({
      reason: "asks_for_money",
      detail: "Asked for a deposit.",
    });
    expect(await screen.findByText(/we have your report/i)).toBeTruthy();
  });

  it("uses the course endpoint for a course", async () => {
    renderUi(<ReportListing kind="course" slug="sterile" />);
    open();
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][0]).toBe("/courses/{slug}/report");
  });

  it("sends no detail when none was written", async () => {
    renderUi(<ReportListing kind="job" slug="a" />);
    open();
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST.mock.calls[0][1].body.detail).toBeUndefined();
  });

  it.each([
    [409, "You manage this listing. You can unpublish it yourself."],
    [409, "You have already reported this listing."],
  ])("shows the server's own sentence for a %s", async (status, detail) => {
    refuse(status, detail);
    renderUi(<ReportListing kind="job" slug="a" />);
    open();
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText(detail)).toBeTruthy();
  });

  it("says it is too many for a 429 and falls back to its own line for anything that said nothing", async () => {
    refuse(429, "Too many reports.");
    const { unmount } = renderUi(<ReportListing kind="job" slug="a" />);
    open();
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText(/several reports today/)).toBeTruthy();
    unmount();

    POST.mockResolvedValue({
      data: undefined,
      error: {},
      response: { status: 500, headers: new Headers() },
    });
    renderUi(<ReportListing kind="job" slug="a" />);
    open();
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(
      await screen.findByText("Could not send your report. Try again."),
    ).toBeTruthy();
  });
});
