// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { THEME_COLOURS, THEME_KEY, applyTheme, getTheme, parseTheme, setTheme, themeScript } from "./theme";

const root = document.documentElement;

function meta(content: string, media: string) {
  const m = document.createElement("meta");
  m.setAttribute("name", "theme-color");
  m.setAttribute("content", content);
  m.setAttribute("media", media);
  document.head.appendChild(m);
  return m;
}

beforeEach(() => {
  localStorage.clear();
  root.removeAttribute("data-theme");
  document.head.innerHTML = "";
});
afterEach(() => vi.restoreAllMocks());

describe("parseTheme", () => {
  it("only light and dark are choices; everything else is the device", () => {
    expect(parseTheme("light")).toBe("light");
    expect(parseTheme("dark")).toBe("dark");
    for (const odd of [null, undefined, "", "system", "Dark", "auto", 3, {}]) expect(parseTheme(odd)).toBe("system");
  });
});

describe("setTheme / getTheme", () => {
  it("remembers a choice, applies it and tells subscribers", () => {
    setTheme("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(getTheme()).toBe("dark");
  });

  it("choosing the device forgets the choice and removes the override", () => {
    setTheme("light");
    setTheme("system");
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    expect(root.hasAttribute("data-theme")).toBe(false);
    expect(getTheme()).toBe("system");
  });

  it("still applies for this visit when storage refuses (a private window)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => setTheme("dark")).not.toThrow();
    expect(root.getAttribute("data-theme")).toBe("dark");
  });

  it("reads 'system' when storage cannot be read", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getTheme()).toBe("system");
  });
});

describe("the address bar", () => {
  it("an override wins over both tags Next wrote, and the device leaves them alone", () => {
    const a = meta(THEME_COLOURS.light, "(prefers-color-scheme: light)");
    const b = meta(THEME_COLOURS.dark, "(prefers-color-scheme: dark)");
    applyTheme("dark");
    for (const m of [a, b]) {
      expect(m.getAttribute("content")).toBe(THEME_COLOURS.dark);
      expect(m.getAttribute("media")).toBe("all");
    }
    const c = meta(THEME_COLOURS.light, "(prefers-color-scheme: light)");
    applyTheme("system");
    expect(c.getAttribute("media")).toBe("(prefers-color-scheme: light)");
  });
});

describe("the script that runs before the first paint", () => {
  const run = () => new Function(themeScript)();

  it("sets a stored override on <html> and on the tags that exist", () => {
    localStorage.setItem(THEME_KEY, "dark");
    const m = meta(THEME_COLOURS.light, "(prefers-color-scheme: light)");
    run();
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(m.getAttribute("content")).toBe(THEME_COLOURS.dark);
  });

  it("does nothing for the device, or for a value it does not know", () => {
    run();
    expect(root.hasAttribute("data-theme")).toBe(false);
    localStorage.setItem(THEME_KEY, "purple");
    run();
    expect(root.hasAttribute("data-theme")).toBe(false);
  });

  it("sets the tags again once the document is parsed, when they did not exist yet", () => {
    localStorage.setItem(THEME_KEY, "light");
    run();
    const late = meta(THEME_COLOURS.dark, "(prefers-color-scheme: dark)");
    document.dispatchEvent(new Event("DOMContentLoaded"));
    expect(late.getAttribute("content")).toBe(THEME_COLOURS.light);
  });

  it("never throws, whatever storage does", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(run).not.toThrow();
  });

  it("is self-contained plain script: no import, no arrow, no let/const", () => {
    expect(themeScript).not.toMatch(/\b(import|export|let|const)\b|=>/);
  });
});
