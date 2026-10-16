"use client";

import { useLocale } from "next-intl";

import { formatCount } from "./count";

export { formatCount } from "./count";

export function useFormatCount(): (n: number) => string {
  const locale = useLocale();
  return (n) => formatCount(n, locale);
}
