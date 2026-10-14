import { DEFAULT_LOCALE, OFFERED_LOCALES, resolveLocale } from "./locale";

describe("which language the app speaks", () => {
  it("takes the first device language it offers", () => {
    expect(resolveLocale(["fr-FR", "hi-IN", "en-GB"])).toBe("hi");
    expect(resolveLocale(["en-IN"])).toBe("en");
  });

  it("accepts an underscore, and any case", () => {
    expect(resolveLocale(["HI_in"])).toBe("hi");
  });

  it("falls back to the default for a language it does not offer", () => {
    expect(resolveLocale(["fr-FR", "de"])).toBe(DEFAULT_LOCALE);
    expect(resolveLocale([])).toBe(DEFAULT_LOCALE);
  });

  it("does not offer Malay, which the web keeps but hides", () => {
    expect(OFFERED_LOCALES).not.toContain("ms");
    expect(resolveLocale(["ms-MY"])).toBe(DEFAULT_LOCALE);
  });
});
