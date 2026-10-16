import { describe, expect, it } from "vitest";

import cases from "../../../tests/fixtures/requirements_cases.json";
import { presentRequirements } from "./requirements";

describe("presentRequirements", () => {
  it("reads the shared fixture (a checker that read nothing would pass)", () => {
    expect(cases.cases.length).toBeGreaterThanOrEqual(6);
  });

  for (const c of cases.cases) {
    it(c.name, () => {
      expect(presentRequirements(c.input)).toEqual(c.expect);
    });
  }
});
