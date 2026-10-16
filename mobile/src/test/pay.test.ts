import cases from "../../../tests/fixtures/pay_cases.json";
import { payLine, yearlyLine } from "../core/pay";

describe("payLine", () => {
  it("reads the shared fixture (a checker that read nothing would pass)", () => {
    expect(cases.cases.length).toBeGreaterThanOrEqual(10);
  });

  for (const c of cases.cases) {
    it(c.name, () => {
      expect(payLine(c.min, c.max, c.type)).toEqual(c.expect);
    });
  }
});

describe("yearlyLine", () => {
  it("keeps the figure as entered", () => {
    expect(yearlyLine(220000, 300000)).toEqual({ unit: "year", shape: "range", min: 220000, max: 300000 });
    expect(yearlyLine(220000, null)).toEqual({ unit: "year", shape: "from", min: 220000 });
    expect(yearlyLine(null, null)).toEqual({ unit: "none", shape: "none" });
  });
});
