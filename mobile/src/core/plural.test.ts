import { createTranslator } from "use-intl/core";

import hi from "../messages/hi.json";
import en from "../messages/en.json";

describe("plural rules for the shared catalogues", () => {
  const original = Intl.PluralRules;

  afterEach(() => {
    Object.defineProperty(Intl, "PluralRules", { value: original, configurable: true, writable: true });
  });

  it("the polyfill, when it is needed, gives English and Hindi their own rules", async () => {
    jest.isolateModules(() => {
      jest.requireActual("@formatjs/intl-pluralrules/polyfill-force.js");
      jest.requireActual("@formatjs/intl-pluralrules/locale-data/en.js");
      jest.requireActual("@formatjs/intl-pluralrules/locale-data/hi.js");
    });
    expect(Intl.PluralRules).not.toBe(original);

    const english = new Intl.PluralRules("en");
    expect([0, 1, 2, 5].map((n) => english.select(n))).toEqual(["other", "one", "other", "other"]);
    // Hindi: zero and one are both "one" (ICU `i = 0 or n = 1`), which English does not do.
    const hindi = new Intl.PluralRules("hi");
    expect([0, 1, 2, 5].map((n) => hindi.select(n))).toEqual(["one", "one", "other", "other"]);
  });

  it("is not installed over an engine that already has the rules", () => {
    const { installPluralRules } = jest.requireActual("./plural-polyfill");
    expect(installPluralRules()).toBe(false);
    expect(Intl.PluralRules).toBe(original);
  });

  it("is installed when the engine lacks Hindi", () => {
    jest.isolateModules(() => {
      jest.doMock("@formatjs/intl-pluralrules/should-polyfill.js", () => ({
        shouldPolyfill: (locale?: string) => (locale === "hi" ? "hi" : undefined),
      }));
      const { installPluralRules } = jest.requireActual("./plural-polyfill");
      expect(installPluralRules()).toBe(true);
    });
    expect([0, 1, 2].map((n) => new Intl.PluralRules("hi").select(n))).toEqual(["one", "one", "other"]);
  });
});

describe("the real catalogues, formatted", () => {
  const t = (locale: "en" | "hi") =>
    createTranslator({ locale, messages: locale === "en" ? en : hi, namespace: "jobsPage" });

  it("English counts jobs", () => {
    const translate = t("en");
    expect(translate("resultsCount", { count: 0 })).toBe("No jobs");
    expect(translate("resultsCount", { count: 1 })).toBe("1 job");
    expect(translate("resultsCount", { count: 7 })).toBe("7 jobs");
  });

  it("Hindi counts jobs through its own message, and a zero stays a zero", () => {
    const translate = t("hi");
    const none = translate("resultsCount", { count: 0 });
    const one = translate("resultsCount", { count: 1 });
    const many = translate("resultsCount", { count: 7 });
    expect(one).toContain("1");
    expect(many).toContain("7");
    expect(none).not.toContain("0 ");
    expect(new Set([none, one, many]).size).toBe(3);
  });
});
