import { describe, expect, it } from "vitest";

import { LOCALES } from "@/i18n/locales";

/** Every key in a message file, flattened to dotted paths. */
function keys(value: unknown, prefix = ""): string[] {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return [prefix];
  return Object.entries(value as Record<string, unknown>).flatMap(([k, v]) =>
    keys(v, prefix ? `${prefix}.${k}` : k),
  );
}

describe("locales", () => {
  it("has more than two, because two hides the assumption", () => {
    // The product was bilingual by construction until Sprint 22: 18 column
    // pairs, 16 API fields and 37 ternaries. A third locale is what proves the
    // shape actually generalises.
    expect(LOCALES.length).toBeGreaterThan(2);
  });

  it("gives every locale a messages file with exactly the same keys", async () => {
    // A missing key is a runtime MISSING_MESSAGE in whichever page happens to
    // use it -- invisible until someone browses in that language.
    const english = new Set(keys((await import("@/messages/en.json")).default));
    for (const locale of LOCALES) {
      const messages = (await import(`@/messages/${locale.code}.json`)).default;
      const theirs = new Set(keys(messages));
      const missing = [...english].filter((k) => !theirs.has(k));
      const extra = [...theirs].filter((k) => !english.has(k));
      expect({ locale: locale.code, missing, extra }).toEqual({
        locale: locale.code,
        missing: [],
        extra: [],
      });
    }
  });

  it("names each language in its own script", () => {
    // Someone looking for Hindi is looking for हिंदी, not for "Hindi".
    expect(LOCALES.map((l) => l.nativeName)).toContain("हिंदी");
    expect(LOCALES.every((l) => l.nativeName.length > 0)).toBe(true);
  });
});
