import { describe, expect, it } from "vitest";

import { courseState, jobState, LISTING_LOOK } from "@/components/cards/listing-look";

/** Sprint 88, BL-19.18: where a vacancy or a course stands on its owner's list. */
describe("jobState", () => {
  const live = { status: "published", is_open: true, taken_down_at: null };

  it("is live for an open published vacancy", () => {
    expect(jobState(live)).toBe("live");
  });

  it("is closed for a published vacancy that is not open: its page is still there, so it is not 'published'", () => {
    expect(jobState({ ...live, is_open: false })).toBe("closed");
  });

  it("is a draft for anything not published, open or not", () => {
    expect(jobState({ status: "draft", is_open: false })).toBe("draft");
    expect(jobState({ status: "draft", is_open: true })).toBe("draft");
  });

  it("is removed when an operator took it down, whatever else is true", () => {
    expect(jobState({ ...live, taken_down_at: "2026-10-01T00:00:00Z" })).toBe("removed");
    expect(jobState({ status: "draft", taken_down_at: "2026-10-01T00:00:00Z" })).toBe("removed");
  });

  it("is closed, not live, when is_open is absent (never guess open)", () => {
    expect(jobState({ status: "published" })).toBe("closed");
  });
});

describe("courseState", () => {
  it("is live when published, a draft otherwise, and removed first", () => {
    expect(courseState({ status: "published" })).toBe("live");
    expect(courseState({ status: "draft" })).toBe("draft");
    expect(courseState({ status: "published", taken_down_at: "2026-10-01T00:00:00Z" })).toBe("removed");
  });

  it("has no closed state", () => {
    for (const status of ["published", "draft", "anything"]) expect(courseState({ status })).not.toBe("closed");
  });
});

describe("LISTING_LOOK", () => {
  it("has a tone and a shape for every state", () => {
    expect(Object.keys(LISTING_LOOK).sort()).toEqual(["closed", "draft", "live", "removed"]);
  });

  it("says each state by tone and by shape, so no two states are alike", () => {
    const seen = new Set(Object.values(LISTING_LOOK).map((l) => `${l.tone}:${l.icon.displayName ?? l.icon.name}`));
    expect(seen.size).toBe(4);
    expect(LISTING_LOOK.removed.tone).toBe("bad");
    expect(LISTING_LOOK.live.tone).toBe("good");
    expect(LISTING_LOOK.draft.tone).toBe("warn");
    expect(LISTING_LOOK.closed.tone).toBe("neutral");
  });
});
