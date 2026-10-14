/**
 * Which language the app speaks. The catalogues are the web app's (`src/messages/*.json`, copied
 * by `make sync-mobile-messages`); the list of languages offered is this file's, because the web
 * hides one it still ships (Malay, ADR-041) and a phone should offer only what is translated.
 *
 * No React Native import: this file is tested in Node.
 */

export const OFFERED_LOCALES = ["en", "hi"] as const;
export type Locale = (typeof OFFERED_LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

/** Whether a stored or received value is one of the languages the app offers. */
export const isLocale = (value: unknown): value is Locale =>
  typeof value === "string" && (OFFERED_LOCALES as readonly string[]).includes(value);

/** `"hi-IN"` -> `"hi"`, `"fr-FR"` -> `"en"`: the first of the device's languages we offer. */
export function resolveLocale(deviceLanguages: readonly string[]): Locale {
  for (const language of deviceLanguages) {
    const base = language.toLowerCase().split(/[-_]/)[0];
    const match = OFFERED_LOCALES.find((locale) => locale === base);
    if (match) return match;
  }
  return DEFAULT_LOCALE;
}
