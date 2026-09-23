import { describe, expect, it } from "vitest";

import { isSignedOut, statusOf } from "@/lib/http";

/**
 * The helper that stops "you are signed out" being rendered as "this is not
 * yours". An owner following written instructions to delete their own
 * organisation found the control absent from the page, because a fifteen
 * minute token had expired and the panel hid itself exactly as it hides from
 * somebody without permission.
 */

describe("statusOf", () => {
  it("reads the status a query function threw", () => {
    expect(statusOf(new Error("401"))).toBe(401);
    expect(statusOf(new Error("403"))).toBe(403);
    expect(statusOf(new Error("404"))).toBe(404);
  });

  it("returns null for the errors that carry no status", () => {
    // The mutations still throw named messages that their call sites read.
    expect(statusOf(new Error("publish-refused"))).toBeNull();
    expect(statusOf(new Error("could not load listings"))).toBeNull();
    expect(statusOf(undefined)).toBeNull();
    expect(statusOf(null)).toBeNull();
    expect(statusOf("401")).toBeNull();
  });

  it("refuses numbers that are not HTTP statuses", () => {
    // Without the range check, a thrown Error("0") or a stray count would be
    // read as a status and could route somebody to a sign-in page for nothing.
    expect(statusOf(new Error("0"))).toBeNull();
    expect(statusOf(new Error("99"))).toBeNull();
    expect(statusOf(new Error("600"))).toBeNull();
    expect(statusOf(new Error("4.01"))).toBeNull();
  });
});

describe("isSignedOut", () => {
  it("is true only for 401", () => {
    expect(isSignedOut(new Error("401"))).toBe(true);
    // 403 is the one that must stay silent: an admin is a member, and a
    // control that always fails is worse than no control.
    expect(isSignedOut(new Error("403"))).toBe(false);
    expect(isSignedOut(new Error("404"))).toBe(false);
    expect(isSignedOut(new Error("500"))).toBe(false);
    expect(isSignedOut(new Error("whatever"))).toBe(false);
  });
});
