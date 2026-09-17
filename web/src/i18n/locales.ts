/**
 * Every language this product offers, in one place (ADR-041).
 *
 * Read by `routing.ts`, the language switcher and the `lang`/`hreflang`
 * attributes, so **adding a language is an entry here plus a messages file** —
 * not a schema migration, not a new API field, and not an edit at 37 render
 * sites. That was the shape before Sprint 22, and the two-tab switcher was its
 * visible symptom.
 *
 * `nativeName` is what a person sees: someone looking for Hindi is looking for
 * "हिंदी", not for "Hindi". `englishName` is for places that must stay legible
 * to an operator, such as a log line or an admin list.
 */
export type LocaleDefinition = {
  code: string;
  nativeName: string;
  englishName: string;
  /** Right-to-left scripts need `dir="rtl"`; none of ours do yet. */
  rtl?: boolean;
};

export const LOCALES: readonly LocaleDefinition[] = [
  { code: "en", nativeName: "English", englishName: "English" },
  { code: "hi", nativeName: "हिंदी", englishName: "Hindi" },
  // A skeleton, and honestly so: navigation and the common actions are
  // translated, everything else falls back to English *visibly* rather than
  // being machine-translated into 650 keys nobody here can check. It earns its
  // place by exercising the machinery at three locales -- two is the number
  // that hides the assumption this sprint removed.
  { code: "ms", nativeName: "Bahasa Melayu", englishName: "Malay" },
] as const;

export const LOCALE_CODES = LOCALES.map((l) => l.code);

export const DEFAULT_LOCALE = "en";

export function localeDefinition(code: string): LocaleDefinition {
  return LOCALES.find((l) => l.code === code) ?? LOCALES[0];
}
