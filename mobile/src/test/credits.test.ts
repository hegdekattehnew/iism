import fixture from "../../../tests/fixtures/credit_cases.json";
import { creditCount, creditsText, type Translate } from "../core/labels";

describe("creditCount", () => {
  it("reads the shared fixture (a checker that read nothing would pass)", () => {
    expect(fixture.cases.length).toBeGreaterThanOrEqual(6);
  });

  for (const c of fixture.cases) {
    it(c.name, () => {
      expect(creditCount(c.credits)).toBe(c.expect);
    });
  }

  it("says nothing for what the API cannot send as JSON", () => {
    expect(creditCount(Number.NaN)).toBeNull();
    expect(creditCount(Number.POSITIVE_INFINITY)).toBeNull();
    expect(creditCount(undefined)).toBeNull();
  });
});

describe("creditsText", () => {
  const t: Translate = (key, values) => `${key}:${values?.count}`;

  it("passes the count to the message and says nothing when there is none", () => {
    expect(creditsText(14, t)).toBe("creditsChip:14");
    expect(creditsText(2.5, t)).toBe("creditsChip:2.5");
    expect(creditsText(0, t)).toBeNull();
    expect(creditsText(null, t)).toBeNull();
  });
});
