import {
  WITHDRAWABLE,
  applyFailureKey,
  canWithdraw,
  isLive,
  withdrawFailureKey,
  type ApplicationStatus,
} from "./applying";

const ALL: ApplicationStatus[] = ["applied", "withdrawn", "shortlisted", "rejected", "hired", "completed", "no_show"];

describe("what a candidate may take back", () => {
  it("is exactly an application nobody has decided", () => {
    expect([...WITHDRAWABLE].sort()).toEqual(["applied", "shortlisted"]);
    for (const status of ALL) {
      expect(canWithdraw(status)).toBe(status === "applied" || status === "shortlisted");
    }
  });

  it("treats a withdrawn application as over and every other as live", () => {
    expect(isLive({ status: "withdrawn" })).toBe(false);
    for (const status of ALL.filter((s) => s !== "withdrawn")) expect(isLive({ status })).toBe(true);
  });
});

describe("how a failed write is named", () => {
  it("says duplicate, daily cap and not-a-seeker for 409, 429 and 403", () => {
    expect(applyFailureKey(409)).toBe("errorDuplicate");
    expect(applyFailureKey(429)).toBe("errorCap");
    expect(applyFailureKey(403)).toBe("errorSeeker");
  });

  it("falls back to the generic line for anything nobody planned for", () => {
    for (const status of [null, 400, 422, 500, 503]) expect(applyFailureKey(status)).toBe("errorGeneric");
  });

  it("says a decision was made when withdrawing meets a 409, and nothing special otherwise", () => {
    expect(withdrawFailureKey(409)).toBe("errorWithdrawDecided");
    expect(withdrawFailureKey(500)).toBe("errorGeneric");
    expect(withdrawFailureKey(429)).toBe("errorGeneric");
  });
});
