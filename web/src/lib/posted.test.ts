import { describe, expect, it } from "vitest";

import fixture from "../../../tests/fixtures/posted_cases.json";
import { postedAgo, postedText, type Translate } from "./job-text";

const now = new Date(fixture.now).getTime();

describe("postedAgo", () => {
  it("reads the shared fixture (a checker that read nothing would pass)", () => {
    expect(fixture.cases.length).toBeGreaterThanOrEqual(12);
    expect(Number.isNaN(now)).toBe(false);
  });

  for (const c of fixture.cases) {
    it(c.name, () => {
      expect(postedAgo(c.posted_at, now)).toEqual(c.expect);
    });
  }

  it("treats undefined as no date", () => {
    expect(postedAgo(undefined, now)).toBeNull();
  });
});

describe("postedText", () => {
  const t: Translate = (key, values) => (values ? `${key}:${values.days}` : key);

  it("says nothing for a vacancy with no date", () => {
    expect(postedText(null, t, now)).toBeNull();
  });

  it("maps each answer to its own message", () => {
    expect(postedText("2026-10-20T11:00:00Z", t, now)).toBe("postedToday");
    expect(postedText("2026-10-19T12:00:00Z", t, now)).toBe("postedYesterday");
    expect(postedText("2026-10-13T12:00:00Z", t, now)).toBe("postedDays:7");
    expect(postedText("2025-01-05T09:30:00Z", t, now)).toBe("postedOverMonth");
  });
});
