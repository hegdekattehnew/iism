import { describe, expect, it } from "vitest";

import { REPLY_WITHIN_DAYS, daysWaiting, isReplyOverdue, replyBy } from "./interest-reply";

const DAY = 24 * 60 * 60 * 1000;
const registered = "2026-10-10T08:00:00Z";
const at = (offsetDays: number) => new Date(registered).getTime() + offsetDays * DAY;

describe("when a reply is expected", () => {
  it("is three days after registering", () => {
    expect(REPLY_WITHIN_DAYS).toBe(3);
    expect(replyBy(registered).toISOString()).toBe("2026-10-13T08:00:00.000Z");
  });

  it("is not overdue on the reply day, and is the moment after it", () => {
    expect(isReplyOverdue(registered, at(0))).toBe(false);
    expect(isReplyOverdue(registered, at(3))).toBe(false);
    expect(isReplyOverdue(registered, at(3) + 1)).toBe(true);
    expect(isReplyOverdue(registered, at(10))).toBe(true);
  });

  it("counts whole days waited and never goes negative", () => {
    expect(daysWaiting(registered, at(0))).toBe(0);
    expect(daysWaiting(registered, at(0) + DAY - 1)).toBe(0);
    expect(daysWaiting(registered, at(4))).toBe(4);
    expect(daysWaiting(registered, at(-2))).toBe(0);
  });
});
