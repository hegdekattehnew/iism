import { NEWS_DAYS, applicationsWithNews, hasNews } from "./home";

const NOW = Date.parse("2026-10-16T06:00:00Z");
const DAY = 86_400_000;
const ago = (days: number) => new Date(NOW - days * DAY).toISOString();
const app = (over: Record<string, unknown> = {}) => ({
  status: "shortlisted" as const,
  status_message: null,
  status_message_at: null,
  updated_at: ago(1),
  ...over,
});

describe("an application with news", () => {
  it("is one an employer has acted on lately", () => {
    for (const status of ["shortlisted", "rejected", "hired", "completed", "no_show"] as const) {
      expect(hasNews(app({ status }), NOW)).toBe(true);
    }
  });

  it("is not one still waiting, or one the person withdrew", () => {
    expect(hasNews(app({ status: "applied" }), NOW)).toBe(false);
    expect(hasNews(app({ status: "withdrawn" }), NOW)).toBe(false);
    expect(hasNews(app({ status: "withdrawn", status_message: "Come on Monday" }), NOW)).toBe(false);
  });

  it("is an applied one that carries a message, since the employer wrote to the person", () => {
    expect(hasNews(app({ status: "applied", status_message: "Please call us" }), NOW)).toBe(true);
    expect(hasNews(app({ status: "applied", status_message: "   " }), NOW)).toBe(false);
  });

  it("stops being news after the window, counting from the message when there is one", () => {
    expect(hasNews(app({ updated_at: ago(NEWS_DAYS) }), NOW)).toBe(true);
    expect(hasNews(app({ updated_at: ago(NEWS_DAYS + 1) }), NOW)).toBe(false);
    // An old status with a fresh message is fresh.
    expect(hasNews(app({ updated_at: ago(60), status_message: "Interview Friday", status_message_at: ago(2) }), NOW)).toBe(true);
    // A fresh touch on an old message is read from the message's own date.
    expect(hasNews(app({ updated_at: ago(1), status_message: "Old", status_message_at: ago(30) }), NOW)).toBe(false);
  });

  it("is not news when the date cannot be read", () => {
    expect(hasNews(app({ updated_at: "not a date" }), NOW)).toBe(false);
  });

  it("is counted, and zero is zero", () => {
    expect(applicationsWithNews([app(), app({ status: "applied" }), app({ updated_at: ago(40) }), app({ status: "hired" })], NOW)).toBe(2);
    expect(applicationsWithNews([], NOW)).toBe(0);
  });
});
