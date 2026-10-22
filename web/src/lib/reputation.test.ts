import { describe, expect, it } from "vitest";

import { MIN_RATINGS_TO_SHOW, ratingDisplay } from "./reputation";

describe("when a rating is shown", () => {
  it("is from three ratings", () => {
    expect(MIN_RATINGS_TO_SHOW).toBe(3);
    expect(ratingDisplay({ average: 4, count: 3 })).toBe("shown");
    expect(ratingDisplay({ average: 5, count: 40 })).toBe("shown");
  });

  it("is withheld, and said to be, below three", () => {
    expect(ratingDisplay({ average: 4, count: 1 })).toBe("few");
    expect(ratingDisplay({ average: 4, count: 2 })).toBe("few");
  });

  it("says nothing for none", () => {
    expect(ratingDisplay(null)).toBe("none");
    expect(ratingDisplay({ average: 0, count: 0 })).toBe("none");
  });
});
