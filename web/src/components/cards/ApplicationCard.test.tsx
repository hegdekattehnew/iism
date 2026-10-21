import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { APPLICATION_LOOK, ApplicationCard, type Application } from "@/components/cards/ApplicationCard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

beforeEach(resetWorld);

const STATUSES = ["applied", "shortlisted", "hired", "rejected", "withdrawn", "completed", "no_show"] as const;

const row = (over: Partial<Application> = {}): Application =>
  ({
    id: "a1",
    status: "applied",
    applied_at: "2026-09-17T10:00:00Z",
    status_message: null,
    status_message_at: null,
    reviewed: false,
    job: { slug: "ward-attendant", title: "Ward Attendant", removed: false, tenant: { name: "Apollo Care Hospitals" } },
    ...over,
  }) as unknown as Application;

/** Sprint 87, BL-19.17: an application on the same card as a vacancy, its state a word and a shape. */
describe("ApplicationCard", () => {
  it("has the employer's mark, the title as a link, the employer, and the date as an icon chip", () => {
    const { container } = renderUi(<ApplicationCard application={row()} />);
    expect(screen.getByRole("link", { name: "Ward Attendant" }).getAttribute("href")).toBe("/jobs/ward-attendant");
    expect(screen.getByText("Apollo Care Hospitals")).toBeTruthy();
    const mark = [...container.querySelectorAll("[aria-hidden='true']")].find((e) => e.textContent === "A");
    expect(mark).toBeTruthy();
    const date = screen.getByText(/Applied on Sep 17, 2026/);
    expect(date.querySelector("svg")).toBeTruthy();
  });

  it("says what the state means in a sentence", () => {
    renderUi(<ApplicationCard application={row()} />);
    expect(screen.getByText("The employer has your application.")).toBeTruthy();
  });

  it.each([
    ["applied", "Applied", "bg-surface-muted"],
    ["shortlisted", "Shortlisted", "bg-success-surface"],
    ["hired", "Hired", "bg-success-surface"],
    ["rejected", "Not selected", "bg-surface-muted"],
    ["withdrawn", "Withdrawn", "bg-warning-surface"],
    ["completed", "Completed", "bg-success-surface"],
    ["no_show", "Did not attend", "bg-warning-surface"],
  ] as const)("draws %s as %s with a shape, on %s", (status, word, token) => {
    renderUi(<ApplicationCard application={row({ status })} />);
    const chip = screen.getByText(word, { selector: "span" });
    expect(chip.querySelector("svg")).toBeTruthy();
    expect(chip.className).toContain(token);
  });

  it("has a look for every status the server can say, and a rejection is neutral, not an alarm", () => {
    expect(Object.keys(APPLICATION_LOOK).sort()).toEqual([...STATUSES].sort());
    expect(APPLICATION_LOOK.rejected.tone).toBe("neutral");
    expect(APPLICATION_LOOK.shortlisted.tone).toBe("good");
    expect(APPLICATION_LOOK.withdrawn.tone).toBe("warn");
    expect(APPLICATION_LOOK.no_show.tone).toBe("warn");
  });

  it("does not tell shortlisted from rejected by tone alone: the shapes differ", () => {
    expect(APPLICATION_LOOK.shortlisted.icon).not.toBe(APPLICATION_LOOK.rejected.icon);
    expect(APPLICATION_LOOK.hired.icon).not.toBe(APPLICATION_LOOK.no_show.icon);
  });

  it("sets the employer's own message apart, with who and when", () => {
    renderUi(
      <ApplicationCard
        application={row({ status: "shortlisted", status_message: "Come on Monday at 10.", status_message_at: "2026-09-20T09:00:00Z" })}
      />,
    );
    expect(screen.getByText("Come on Monday at 10.")).toBeTruthy();
    expect(screen.getByText(/A message from Apollo Care Hospitals · Sep 20, 2026/)).toBeTruthy();
  });

  it("shows no message block when there is none", () => {
    renderUi(<ApplicationCard application={row()} />);
    expect(screen.queryByText(/A message from Apollo Care Hospitals/)).toBeNull();
  });

  it("says a vacancy an operator removed is removed, and does not link to a page that is gone", () => {
    renderUi(<ApplicationCard application={row({ job: { slug: "gone", title: "Ward Attendant", removed: true, tenant: { name: "Apollo Care Hospitals" } } as never })} />);
    expect(screen.getByText("Removed by our team")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Ward Attendant" })).toBeNull();
  });

  it("puts what the list passes in as a footer under everything else", () => {
    renderUi(<ApplicationCard application={row()} footer={<button type="button">Why not me?</button>} />);
    expect(screen.getByRole("button", { name: "Why not me?" })).toBeTruthy();
  });
});
