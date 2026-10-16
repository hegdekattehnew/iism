/**
 * Indian digit grouping for Hindi and Indian English alike: 2,38,370, not 238,370.
 *
 * One place (Sprint 50.5): `StatsBand` and `LiveCount` each wrote this, and two copies of a
 * formatting rule are how one number on a page ends up grouped differently from the one beside it.
 *
 * Its own file without `"use client"` (Sprint 69): `format.ts` carries a hook, so it is a client
 * module, and a server component cannot call a function exported from one. `format.ts` re-exports
 * this, so existing imports are unchanged.
 */
export function formatCount(n: number, locale: string): string {
  return new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(n);
}
