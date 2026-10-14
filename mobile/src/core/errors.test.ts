import { ApiError, isSignedOut, isUpgradeRequired, readDetail, statusOf } from "./errors";

describe("failures keep what the server said", () => {
  it("reads a string detail", () => {
    expect(readDetail({ detail: "Incorrect or expired code" })).toBe("Incorrect or expired code");
  });

  it("joins the messages of a 422", () => {
    const body = { detail: [{ loc: ["body", "phone"], msg: "Field required" }, { msg: "Too short" }] };
    expect(readDetail(body)).toBe("Field required. Too short");
  });

  it("says nothing rather than something wrong", () => {
    expect(readDetail(null)).toBeNull();
    expect(readDetail({ detail: 5 })).toBeNull();
    expect(readDetail({ detail: [] })).toBeNull();
  });

  it("keeps the detail as the message", () => {
    expect(new ApiError(422, "Too short").message).toBe("Too short");
    expect(new ApiError(500, null).message).toBe("500");
  });

  it("tells 'signed out' from 'not yours' and from 'update the app'", () => {
    expect(isSignedOut(new ApiError(401, null))).toBe(true);
    expect(isSignedOut(new ApiError(403, null))).toBe(false);
    expect(isUpgradeRequired(new ApiError(426, null))).toBe(true);
    expect(statusOf(new Error("404"))).toBe(404);
    expect(statusOf(new Error("nope"))).toBeNull();
  });
});
