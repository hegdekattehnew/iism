import { defineRouting } from "next-intl/routing";

// Hindi and English are both live from day one (ADR-033). Adding a locale is a
// translation task, not a refactor, because nothing is hardcoded to English.
export const routing = defineRouting({
  locales: ["en", "hi"] as const,
  defaultLocale: "en",
});

export type Locale = (typeof routing.locales)[number];
