import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobCard } from "@/components/cards/JobCard";
import { daysToClose } from "@/lib/job-text";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const NOW = Date.parse("2026-10-16T06:00:00Z");
const DAY = 86_400_000;

const JOB = {
  slug: "gda-chennai",
  title: "General Duty Assistant",
  location_state: "Tamil Nadu",
  location_district: "Chennai",
  employment_type: "full_time",
  experience_min_years: 0,
  experience_max_years: 2,
  salary_min_inr: 220000,
  salary_max_inr: 300000,
  closes_at: null as string | null,
  nsqf_level_min: 3,
  tenant: { name: "Apollo Care", is_verified: true },
};

beforeEach(resetWorld);

/** Sprint 69, UI-04/05/10: what a card says, and what it will not say. */
describe("JobCard", () => {
  it("leads with what a person asks first: who, where, how much a month", () => {
    renderUi(<JobCard job={JOB} now={NOW} />);
    expect(screen.getByRole("heading", { name: "General Duty Assistant" })).toBeTruthy();
    expect(screen.getByText(/^Apollo Care/)).toBeTruthy();
    expect(screen.getByText("Chennai, Tamil Nadu")).toBeTruthy();
    expect(screen.getByText("About ₹18,300–25,000 a month")).toBeTruthy();
  });

  it("does not print the yearly figure or the NSQF level on the card", () => {
    const { container } = renderUi(<JobCard job={JOB} now={NOW} />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/per year/);
    expect(text).not.toMatch(/2,20,000|3,00,000/);
    expect(text).not.toMatch(/NSQF/);
  });

  it("marks a verified employer, and says nothing at all about one that is not", () => {
    renderUi(<JobCard job={JOB} now={NOW} />);
    expect(screen.getByText("Verified employer")).toBeTruthy();
  });

  it("never says 'not verified' on a card (that sentence belongs on the vacancy page)", () => {
    const { container } = renderUi(
      <JobCard job={{ ...JOB, tenant: { name: "Apollo Care", is_verified: false } }} now={NOW} />,
    );
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/verified/i);
  });

  it("shows the employment type only when it is not the ordinary one", () => {
    const ordinary = renderUi(<JobCard job={JOB} now={NOW} />);
    expect(screen.queryByText("Full time")).toBeNull();
    ordinary.unmount();
    renderUi(<JobCard job={{ ...JOB, employment_type: "part_time" }} now={NOW} />);
    expect(screen.getByText("Part time")).toBeTruthy();
  });

  it("a gig keeps its posted figure and is never turned into a month", () => {
    renderUi(
      <JobCard
        job={{ ...JOB, employment_type: "gig", salary_min_inr: 5000, salary_max_inr: 8000 }}
        now={NOW}
      />,
    );
    expect(screen.getByText("₹5,000–8,000 as posted")).toBeTruthy();
    expect(screen.queryByText(/a month/)).toBeNull();
  });

  it("says when the pay is not stated", () => {
    renderUi(<JobCard job={{ ...JOB, salary_min_inr: null, salary_max_inr: null }} now={NOW} />);
    expect(screen.getByText("Salary not disclosed")).toBeTruthy();
  });

  it("says how soon it closes, only when that is near", () => {
    const soon = new Date(NOW + 3 * DAY - 1000).toISOString();
    const near = renderUi(<JobCard job={{ ...JOB, closes_at: soon }} now={NOW} />);
    expect(screen.getByText("Closes in 3 days")).toBeTruthy();
    near.unmount();
    renderUi(<JobCard job={{ ...JOB, closes_at: new Date(NOW + 90 * DAY).toISOString() }} now={NOW} />);
    expect(screen.queryByText(/Closes in/)).toBeNull();
  });
});

describe("how long ago it was posted (Sprint 74)", () => {
  it("says so in the words of the elapsed days", () => {
    const today = renderUi(
      <JobCard job={{ ...JOB, published_at: new Date(NOW - 3_600_000).toISOString() }} now={NOW} />,
    );
    expect(screen.getByText("Posted today")).toBeTruthy();
    today.unmount();
    const three = renderUi(
      <JobCard job={{ ...JOB, published_at: new Date(NOW - 3 * DAY - 1000).toISOString() }} now={NOW} />,
    );
    expect(screen.getByText("Posted 3 days ago")).toBeTruthy();
    three.unmount();
    renderUi(
      <JobCard job={{ ...JOB, published_at: new Date(NOW - 90 * DAY).toISOString() }} now={NOW} />,
    );
    expect(screen.getByText("Posted over a month ago")).toBeTruthy();
  });

  it("says nothing for a vacancy with no date, rather than something made up", () => {
    renderUi(<JobCard job={{ ...JOB, published_at: null }} now={NOW} />);
    expect(screen.queryByText(/Posted/)).toBeNull();
  });
});

describe("daysToClose", () => {
  it("is null for no date, a past date, a date beyond 30 days or one that is not a date", () => {
    expect(daysToClose(null, NOW)).toBeNull();
    expect(daysToClose(new Date(NOW - DAY).toISOString(), NOW)).toBeNull();
    expect(daysToClose(new Date(NOW + 31 * DAY).toISOString(), NOW)).toBeNull();
    expect(daysToClose("not a date", NOW)).toBeNull();
  });

  it("rounds a part of a day up, and counts 30 days in", () => {
    expect(daysToClose(new Date(NOW + 3 * 3_600_000).toISOString(), NOW)).toBe(1);
    expect(daysToClose(new Date(NOW + 30 * DAY).toISOString(), NOW)).toBe(30);
  });
});

/** Sprint 84, BL-19.15: the avatar-and-icon-chip card, and the score a signed-in seeker sees on it. */
describe("card v3", () => {
  it("has the employer's mark beside the title, hidden from a screen reader", () => {
    const { container } = renderUi(<JobCard job={JOB} now={NOW} />);
    const mark = container.querySelector('[aria-hidden="true"]') as HTMLElement;
    expect(mark.textContent).toBe("A");
  });

  it("draws the pay and the place as chips with an icon each", () => {
    renderUi(<JobCard job={JOB} now={NOW} />);
    const pay = screen.getByText("About ₹18,300–25,000 a month");
    const place = screen.getByText("Chennai, Tamil Nadu");
    expect(pay.className).toContain("bg-accent-soft");
    expect(pay.querySelector("svg")).toBeTruthy();
    expect(place.className).toContain("bg-surface-muted");
    expect(place.querySelector("svg")).toBeTruthy();
  });

  it("has no place chip for a vacancy with no place", () => {
    const { container } = renderUi(
      <JobCard job={{ ...JOB, location_state: null, location_district: null }} now={NOW} />,
    );
    expect(container.querySelectorAll("svg").length).toBe(2); // the rupee and the verified mark
  });

  it("is a link to the vacancy", () => {
    renderUi(<JobCard job={JOB} now={NOW} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/jobs/gda-chennai");
  });
});

describe("the match score on a card (UI-04)", () => {
  it("shows the person's score when there is one", () => {
    renderUi(<JobCard job={JOB} now={NOW} score={87} scoreSlot />);
    expect(screen.getByText("87% match")).toBeTruthy();
  });

  it("shows a score of zero, which is a score, and nothing for no score", () => {
    const zero = renderUi(<JobCard job={JOB} now={NOW} score={0} scoreSlot />);
    expect(screen.getByText("0% match")).toBeTruthy();
    zero.unmount();
    renderUi(<JobCard job={JOB} now={NOW} scoreSlot />);
    expect(screen.queryByText(/% match/)).toBeNull();
  });

  it("leaves the title room for a score before it arrives, and does not for a visitor", () => {
    const seeker = renderUi(<JobCard job={JOB} now={NOW} scoreSlot />);
    expect(seeker.container.querySelector("h2")?.parentElement?.className).toContain("pr-24");
    seeker.unmount();
    const visitor = renderUi(<JobCard job={JOB} now={NOW} />);
    expect(visitor.container.querySelector("h2")?.parentElement?.className).not.toContain("pr-24");
  });

  it("keeps the same room whether or not the score has landed (so the title never re-wraps)", () => {
    const before = renderUi(<JobCard job={JOB} now={NOW} scoreSlot />);
    const room = before.container.querySelector("h2")?.parentElement?.className;
    before.unmount();
    const after = renderUi(<JobCard job={JOB} now={NOW} scoreSlot score={72} />);
    expect(after.container.querySelector("h2")?.parentElement?.className).toBe(room);
  });
});
