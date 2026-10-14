import { formatDate, formatInr } from "./format";

const months = (m: number, style: "short" | "long") =>
  (style === "short"
    ? ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    : ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])[m];

describe("Indian digit grouping", () => {
  it.each([
    [0, "0"],
    [7, "7"],
    [999, "999"],
    [1000, "1,000"],
    [99999, "99,999"],
    [100000, "1,00,000"],
    [238370, "2,38,370"],
    [9999999, "99,99,999"],
    [10000000, "1,00,00,000"],
    [123456789, "12,34,56,789"],
  ])("%d is %s", (n, expected) => {
    expect(formatInr(n)).toBe(expected);
  });

  it("keeps a minus sign and rounds a fraction away", () => {
    expect(formatInr(-238370)).toBe("-2,38,370");
    expect(formatInr(1499.6)).toBe("1,500");
  });

  it("does not print a minus for something that rounds to zero", () => {
    expect(formatInr(-0.2)).toBe("0");
  });

  it("returns nothing for something that is not a number", () => {
    expect(formatInr(Number.NaN)).toBe("");
    expect(formatInr(Number.POSITIVE_INFINITY)).toBe("");
  });
});

describe("a calendar date", () => {
  it("is read from its text, in either length", () => {
    expect(formatDate("2026-10-14", months)).toBe("14 Oct 2026");
    expect(formatDate("2026-10-14", months, "long")).toBe("14 October 2026");
  });

  it("does not drift by a day around midnight, in any timezone", () => {
    const zone = process.env.TZ;
    for (const tz of ["Pacific/Auckland", "America/Los_Angeles", "Asia/Kolkata", "UTC"]) {
      process.env.TZ = tz;
      expect(formatDate("2026-01-01", months)).toBe("1 Jan 2026");
      expect(formatDate("2026-12-31", months)).toBe("31 Dec 2026");
    }
    process.env.TZ = zone;
  });

  it("accepts a leap day only in a leap year", () => {
    expect(formatDate("2028-02-29", months)).toBe("29 Feb 2028");
    expect(formatDate("2026-02-29", months)).toBeNull();
    expect(formatDate("2100-02-29", months)).toBeNull();
    expect(formatDate("2000-02-29", months)).toBe("29 Feb 2000");
  });

  it("returns nothing for anything that is not a real date, never a wrong one", () => {
    for (const bad of ["", "tomorrow", "2026-13-01", "2026-00-10", "2026-04-31", "14/10/2026"]) {
      expect(formatDate(bad, months)).toBeNull();
    }
  });

  it("reads the date part of a timestamp without converting it", () => {
    expect(formatDate("2026-10-14T23:30:00Z", months)).toBe("14 Oct 2026");
  });
});
