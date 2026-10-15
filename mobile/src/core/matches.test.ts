import { coveragePercent, localityKey } from "./matches";

describe("reading a match", () => {
  it("shows coverage as a whole percentage, kept inside 0 to 100", () => {
    expect(coveragePercent(0.5)).toBe(50);
    expect(coveragePercent(0.666)).toBe(67);
    expect(coveragePercent(0)).toBe(0);
    expect(coveragePercent(1)).toBe(100);
    expect(coveragePercent(1.4)).toBe(100);
    expect(coveragePercent(-0.2)).toBe(0);
  });

  it("names the district and the state, and says nothing otherwise", () => {
    expect(localityKey(2)).toBe("nearDistrict");
    expect(localityKey(1)).toBe("nearState");
    expect(localityKey(0)).toBeNull();
    expect(localityKey(undefined)).toBeNull();
    expect(localityKey(null)).toBeNull();
  });
});
