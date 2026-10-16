/**
 * What a posted salary is called by the people reading it (Sprint 69, UI-05).
 *
 * The API stores one annual figure. A person looking for work at this level is told, and tells
 * others, what they earn **a month**, so the card says that. The rule is pure and the phone has the
 * same one (`mobile/src/core/pay.ts`); both are tested against `tests/fixtures/pay_cases.json`, so
 * the two cannot drift.
 */

/** Types whose posted figure is a salary: a month is that figure over twelve. */
const SALARIED = new Set(["full_time", "part_time", "contract", "apprenticeship"]);

export type PayLine =
  | { unit: "none"; shape: "none" }
  | { unit: "month" | "year" | "posted"; shape: "range"; min: number; max: number }
  | { unit: "month" | "year" | "posted"; shape: "from" | "exact"; min: number };

const nearestHundred = (n: number) => Math.round(n / 100) * 100;

/**
 * `min` alone is "from"; a maximum with no minimum says nothing (it is not invented into a range);
 * a gig keeps its figure as posted; a figure under about ₹600 a year would read "₹0 a month", so it
 * stays annual.
 */
export function payLine(
  min: number | null | undefined,
  max: number | null | undefined,
  employmentType: string,
): PayLine {
  if (!min) return { unit: "none", shape: "none" };
  const hasMax = Boolean(max);
  if (!SALARIED.has(employmentType)) {
    return hasMax
      ? { unit: "posted", shape: "range", min, max: max as number }
      : { unit: "posted", shape: "from", min };
  }
  const low = nearestHundred(min / 12);
  if (low === 0) {
    return hasMax
      ? { unit: "year", shape: "range", min, max: max as number }
      : { unit: "year", shape: "from", min };
  }
  if (!hasMax) return { unit: "month", shape: "from", min: low };
  const high = nearestHundred((max as number) / 12);
  return high === low
    ? { unit: "month", shape: "exact", min: low }
    : { unit: "month", shape: "range", min: low, max: high };
}

/** The same figure as the vacancy page's second line: the posted annual amount, as it was entered. */
export function yearlyLine(
  min: number | null | undefined,
  max: number | null | undefined,
): PayLine {
  if (!min) return { unit: "none", shape: "none" };
  return max
    ? { unit: "year", shape: "range", min, max }
    : { unit: "year", shape: "from", min };
}
