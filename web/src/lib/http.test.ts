import { describe, expect, it } from "vitest";

import { ApiError, detailOf, isSignedOut, readDetail, statusOf } from "@/lib/http";

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
    // Sprint 30 removed the last mutations that threw a named sentinel --
    // `publish-refused` and `close-failed` -- because the screen then showed
    // one fixed sentence for every failure, including an expired session.
    // The behaviour stays pinned: anything that is not a status reads as none.
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

describe("readDetail", () => {
  it("reads a raised HTTPException's message", () => {
    // What the API says when a standard does not exist.
    expect(readDetail({ detail: "Unknown standards: welding-x" })).toBe(
      "Unknown standards: welding-x",
    );
  });

  it("names the field in a 422, which is the whole point", () => {
    // The reported bug: a two-character title produced "Could not save" and
    // nothing else, while the server had said exactly this.
    expect(
      readDetail({
        detail: [
          {
            type: "string_too_short",
            loc: ["body", "title"],
            msg: "String should have at least 3 characters",
          },
        ],
      }),
    ).toBe("Title: String should have at least 3 characters");
  });

  it("finds the field inside a nested location", () => {
    // Still the nesting that is under test: `skill_slug` is four levels into
    // `loc`, and reaching it is what lets it be labelled at all.
    expect(
      readDetail({
        detail: [{ loc: ["body", "skills", 0, "skill_slug"], msg: "Field required" }],
      }),
    ).toBe("Standard: Field required");
  });

  it("falls back to the raw field name when there is no label for it", () => {
    // The map is a courtesy, not a gate -- a field nobody has named yet must
    // still reach the screen rather than being dropped.
    expect(readDetail({ detail: [{ loc: ["body", "wat"], msg: "nope" }] })).toBe(
      "wat: nope",
    );
  });

  it("joins several field errors", () => {
    const out = readDetail({
      detail: [
        { loc: ["body", "title"], msg: "too short" },
        { loc: ["body", "positions"], msg: "must be positive" },
      ],
    });
    expect(out).toBe("Title: too short. How many people: must be positive");
  });

  it("returns null rather than inventing something", () => {
    // A network failure or a 500 carries nothing worth showing, and the
    // caller falls back to its own sentence.
    expect(readDetail(null)).toBeNull();
    expect(readDetail("boom")).toBeNull();
    expect(readDetail({})).toBeNull();
    expect(readDetail({ detail: [] })).toBeNull();
    expect(readDetail({ detail: [{ loc: ["body"] }] })).toBeNull();
  });
});

describe("ApiError", () => {
  it("carries both the status and what the server said", () => {
    const e = new ApiError(422, "Title: too short");
    expect(statusOf(e)).toBe(422);
    expect(detailOf(e)).toBe("Title: too short");
    expect(e.message).toBe("Title: too short");
  });

  it("still routes a 401 to the signed-out branch", () => {
    // The two fixes have to coexist: a 401 with a detail is still a 401.
    expect(isSignedOut(new ApiError(401, "Not authenticated"))).toBe(true);
  });

  it("falls back to the status when there is no detail", () => {
    const e = new ApiError(500, null);
    expect(statusOf(e)).toBe(500);
    expect(detailOf(e)).toBeNull();
    expect(e.message).toBe("500");
  });

  it("has no detail to give for an ordinary Error", () => {
    expect(detailOf(new Error("403"))).toBeNull();
  });
});
