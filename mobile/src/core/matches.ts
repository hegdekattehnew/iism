/**
 * Reading a match. The phone renders the scorer's fields and **computes nothing about a score**
 * (ADR-037: one scorer, and a picture that derives its own number can disagree with the one it
 * explains). The two helpers here only turn a field into words.
 *
 * No React Native import.
 */

/** `coverage` is a fraction of the weighted requirements; people read a percentage. */
export function coveragePercent(coverage: number): number {
  return Math.round(Math.min(1, Math.max(0, coverage)) * 100);
}

/**
 * Locality only orders equal scores, so the label says *where*, never "better": 2 is the person's
 * own district, 1 their state, anything else says nothing.
 */
export function localityKey(locality: number | null | undefined): "nearDistrict" | "nearState" | null {
  if (locality === 2) return "nearDistrict";
  if (locality === 1) return "nearState";
  return null;
}
