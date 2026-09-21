import { defineRouting } from "next-intl/routing";

import { DEFAULT_LOCALE, LOCALE_CODES } from "./locales";

// The list lives in `locales.ts` (ADR-041) so that routing, the switcher and
// the `hreflang` tags cannot disagree about which languages exist. Adding one
// is an entry there and a messages file -- nothing here changes.
export const routing = defineRouting({
  locales: LOCALE_CODES,
  defaultLocale: DEFAULT_LOCALE,
});

export type Locale = string;
