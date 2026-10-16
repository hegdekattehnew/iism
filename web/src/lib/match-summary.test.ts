import { describe, expect, it } from "vitest";

import cases from "../../../tests/fixtures/match_summary_cases.json";
import { matchSummary } from "./match-summary";

describe("matchSummary", () => {
  it("reads the shared fixture (a checker that read nothing would pass)", () => {
    expect(cases.cases.length).toBeGreaterThanOrEqual(8);
  });

  for (const c of cases.cases) {
    it(c.name, () => {
      expect(matchSummary(c.matched, c.missing)).toEqual(c.expect);
    });
  }
});
