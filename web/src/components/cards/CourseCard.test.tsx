import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CourseCard, type Course } from "@/components/cards/CourseCard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const COURSE: Course = {
  slug: "phlebotomy-pune",
  title: "Phlebotomy basics",
  description: "Learn to draw blood safely.",
  mode: "offline",
  language: "en",
  duration_hours: 120,
  fee_inr: 4500,
  nsqf_level: 4,
  qualification_credits: null,
  location_state: "Maharashtra",
  location_district: "Pune",
  starts_on: "2026-11-02",
  started: false,
  tenant: { name: "Skill Forge" },
};

beforeEach(resetWorld);

/** Sprint 84, BL-19.15: a course on the same card as a vacancy. */
describe("CourseCard", () => {
  it("leads with the provider's mark, the title and the provider", () => {
    const { container } = renderUi(<CourseCard course={COURSE} />);
    expect(screen.getByRole("heading", { name: "Phlebotomy basics" })).toBeTruthy();
    expect(screen.getByText("Skill Forge")).toBeTruthy();
    expect((container.querySelector('[aria-hidden="true"]') as HTMLElement).textContent).toBe("S");
  });

  it("draws the fee, the place and the start as chips with an icon each", () => {
    renderUi(<CourseCard course={COURSE} />);
    const fee = screen.getByText("₹4,500");
    expect(fee.className).toContain("bg-accent-soft");
    expect(fee.querySelector("svg")).toBeTruthy();
    expect(screen.getByText("Pune, Maharashtra").querySelector("svg")).toBeTruthy();
    expect(screen.getByText(/Starts/).querySelector("svg")).toBeTruthy();
  });

  it("says free for a fee of zero or none", () => {
    const zero = renderUi(<CourseCard course={{ ...COURSE, fee_inr: 0 }} />);
    expect(screen.getByText("Free")).toBeTruthy();
    zero.unmount();
    renderUi(<CourseCard course={{ ...COURSE, fee_inr: null }} />);
    expect(screen.getByText("Free")).toBeTruthy();
  });

  it("has no place for an online course, and says a started one has started", () => {
    renderUi(<CourseCard course={{ ...COURSE, mode: "online", started: true }} />);
    expect(screen.queryByText("Pune, Maharashtra")).toBeNull();
    expect(screen.getByText(/Started/)).toBeTruthy();
  });

  it("has no date chip when it has no start", () => {
    renderUi(<CourseCard course={{ ...COURSE, starts_on: null }} />);
    expect(screen.queryByText(/Starts|Started/)).toBeNull();
  });

  it("keeps the facts a learner compares in one muted line, and the credits only when finite and above zero", () => {
    const some = renderUi(<CourseCard course={{ ...COURSE, qualification_credits: 12 }} />);
    expect(some.container.textContent).toMatch(/12/);
    some.unmount();
    const none = renderUi(<CourseCard course={{ ...COURSE, qualification_credits: 0 }} />);
    expect(none.container.textContent).not.toMatch(/credit/i);
  });

  it("is a link to the course", () => {
    renderUi(<CourseCard course={COURSE} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/courses/phlebotomy-pune");
  });
});
