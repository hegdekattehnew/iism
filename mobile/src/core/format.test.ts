import { formatInstantDate, formatDate, formatInr } from "./format";

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


describe("the day a moment happened, in India", () => {
  const month = (m: number, style: string) => `${style}-m${m + 1}`;

  it("moves a late-evening UTC moment to the next Indian day", () => {
    expect(formatInstantDate("2026-10-14T20:00:00+00:00", month)).toBe("15 short-m10 2026");
    expect(formatInstantDate("2026-10-14T18:29:00Z", month)).toBe("14 short-m10 2026");
    expect(formatInstantDate("2026-10-14T18:30:00Z", month)).toBe("15 short-m10 2026");
  });

  it("honours an offset the API names, across a month and a year end", () => {
    expect(formatInstantDate("2026-12-31T23:00:00-05:00", month)).toBe("1 short-m1 2027");
    expect(formatInstantDate("2026-10-14T01:00:00+05:30", month)).toBe("14 short-m10 2026");
  });

  it("copes with the microseconds the API sends and with no offset at all", () => {
    expect(formatInstantDate("2026-10-14T10:20:30.123456+00:00", month, "long")).toBe("14 long-m10 2026");
    expect(formatInstantDate("2026-10-14T10:20:30.123456", month)).toBe("14 short-m10 2026");
  });

  it("knows a leap day", () => {
    expect(formatInstantDate("2028-02-29T10:00:00Z", month)).toBe("29 short-m2 2028");
    expect(formatInstantDate("2027-02-29T10:00:00Z", month)).toBeNull();
  });

  it("returns null, never a wrong day, for anything else", () => {
    for (const bad of ["", "yesterday", "2026-13-01T00:00:00Z", "2026-10-14", "2026-10-14T25:00:00Z"]) {
      expect(formatInstantDate(bad, month)).toBeNull();
    }
  });
});
