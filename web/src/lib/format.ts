"use client";

import { useLocale } from "next-intl";

/**
 * Indian digit grouping for Hindi and Indian English alike: 2,38,370, not 238,370.
 *
 * One place (Sprint 50.5). `StatsBand` and `LiveCount` each wrote this, and two copies of a
 * formatting rule are how one number on a page ends up grouped differently from the one
 * beside it -- which reads as a different kind of number rather than a larger one.
 */
export function formatCount(n: number, locale: string): string {
  return new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(n);
}

export function useFormatCount(): (n: number) => string {
  const locale = useLocale();
  return (n) => formatCount(n, locale);
}
