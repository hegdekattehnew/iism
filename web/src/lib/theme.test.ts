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
  it("dark and system are choices; everything else is the default, light", () => {
    expect(parseTheme("dark")).toBe("dark");
    expect(parseTheme("system")).toBe("system");
    expect(parseTheme("light")).toBe("light");
    for (const odd of [null, undefined, "", "Dark", "auto", 3, {}]) expect(parseTheme(odd)).toBe("light");
  });
});

describe("setTheme / getTheme", () => {
  it("is light until somebody chooses", () => {
    expect(getTheme()).toBe("light");
    expect(root.hasAttribute("data-theme")).toBe(false);
  });

  it("remembers dark, applies it and tells subscribers", () => {
    setTheme("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(getTheme()).toBe("dark");
  });

  it("remembers 'match the device' as its own choice", () => {
    setTheme("system");
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
    expect(root.getAttribute("data-theme")).toBe("system");
    expect(getTheme()).toBe("system");
  });

  it("choosing light forgets the choice and removes the attribute, because light is the default", () => {
    setTheme("dark");
    setTheme("light");
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    expect(root.hasAttribute("data-theme")).toBe(false);
    expect(getTheme()).toBe("light");
  });

  it("still applies for this visit when storage refuses (a private window)", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => setTheme("dark")).not.toThrow();
    expect(root.getAttribute("data-theme")).toBe("dark");
  });

  it("reads light when storage cannot be read", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getTheme()).toBe("light");
  });
});

function deviceIs(scheme: "dark" | "light") {
  window.matchMedia = ((query: string) => ({
    matches: scheme === "dark" && query.includes("dark"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia;
}

describe("the address bar", () => {
  it("there is one tag, light by default; a choice changes its colour and 'match device' reads the device", () => {
    const m = meta(THEME_COLOURS.light, "all");
    applyTheme("dark");
    expect(m.getAttribute("content")).toBe(THEME_COLOURS.dark);
    expect(m.hasAttribute("media")).toBe(false);
    applyTheme("light");
    expect(m.getAttribute("content")).toBe(THEME_COLOURS.light);
    deviceIs("dark");
    applyTheme("system");
    expect(m.getAttribute("content")).toBe(THEME_COLOURS.dark);
    deviceIs("light");
    applyTheme("system");
    expect(m.getAttribute("content")).toBe(THEME_COLOURS.light);
  });
});

describe("the script that runs before the first paint", () => {
  const run = () => new Function(themeScript)();

  it("sets a stored dark on <html> and on the tag that exists", () => {
    localStorage.setItem(THEME_KEY, "dark");
    const m = meta(THEME_COLOURS.light, "all");
    run();
    expect(root.getAttribute("data-theme")).toBe("dark");
    expect(m.getAttribute("content")).toBe(THEME_COLOURS.dark);
  });

  it("sets 'system' and takes the address-bar colour from the device", () => {
    localStorage.setItem(THEME_KEY, "system");
    deviceIs("dark");
    const m = meta(THEME_COLOURS.light, "all");
    run();
    expect(root.getAttribute("data-theme")).toBe("system");
    expect(m.getAttribute("content")).toBe(THEME_COLOURS.dark);
  });

  it("does nothing for the default, or for a value it does not know (light needs no script)", () => {
    run();
    expect(root.hasAttribute("data-theme")).toBe(false);
    for (const odd of ["purple", "light"]) {
      localStorage.setItem(THEME_KEY, odd);
      run();
      expect(root.hasAttribute("data-theme")).toBe(false);
    }
  });

  it("sets the tag again once the document is parsed, when it did not exist yet", () => {
    localStorage.setItem(THEME_KEY, "dark");
    run();
    const late = meta(THEME_COLOURS.light, "all");
    document.dispatchEvent(new Event("DOMContentLoaded"));
    expect(late.getAttribute("content")).toBe(THEME_COLOURS.dark);
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
