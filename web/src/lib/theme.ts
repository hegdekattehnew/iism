/**
 * Light, dark, or follow the device (Sprint 78, BL-19.8, ADR-087).
 *
 * The product has always followed `prefers-color-scheme`. A person can now **override** it, and the
 * choice is held in this browser only (`localStorage`, never the account: it is a taste of one
 * screen, not a fact about the person, and ADR-055 would otherwise make it a column to export and
 * erase). "System" is the absence of a choice, so a person who never touches the control gets
 * exactly what they got before.
 *
 * The override is the attribute `data-theme="light" | "dark"` on `<html>`; `globals.css` answers it
 * with a second copy of the dark tokens and a light pin, and a test holds the copy equal to the
 * media query's. The attribute must be there **before the first paint**, or a person who chose dark
 * sees a white page flash on every load, so it is set by a small script in `<head>` that runs
 * before the body is parsed (`themeScript`), built from the same constants as the code below so
 * they cannot drift. The CSP allows inline script (CLAUDE.md, the CSP entry).
 *
 * No React in this file: the switch component reads it through `useSyncExternalStore`.
 */

export const THEME_KEY = "iism-theme";
export const THEMES = ["system", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

/** The browser's address bar colour for each theme: the page background of `globals.css`. */
export const THEME_COLOURS = { light: "#f8f9fa", dark: "#111417" } as const;

/** A stored value is a choice only if it is one of the two overrides; anything else is "system". */
export function parseTheme(raw: unknown): Theme {
  return raw === "light" || raw === "dark" ? raw : "system";
}

const listeners = new Set<() => void>();

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null; // private windows and blocked site data throw on access
  }
}

export function getTheme(): Theme {
  if (typeof window === "undefined") return "system";
  try {
    return parseTheme(storage()?.getItem(THEME_KEY) ?? null);
  } catch {
    return "system"; // reading can throw as well as access: blocked site data, a full quota
  }
}

/** Put a choice on the page: the attribute CSS answers, and the browser's own chrome. */
export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    // Next writes one tag per scheme, each with a `media`; an override has to win over both.
    if (theme === "system") continue;
    meta.setAttribute("media", "all");
    meta.setAttribute("content", THEME_COLOURS[theme]);
  }
}

/**
 * Remember a choice and apply it. "System" forgets the choice and returns to the media query; the
 * address-bar colour is then restored on the next load (the tags Next wrote carry the right `media`
 * again), which is the one thing a switch back cannot do live.
 */
export function setTheme(theme: Theme): void {
  const store = storage();
  try {
    if (theme === "system") store?.removeItem(THEME_KEY);
    else store?.setItem(THEME_KEY, theme);
  } catch {
    // Storage refused: the choice still applies for this visit.
  }
  applyTheme(theme);
  listeners.forEach((listener) => listener());
}

/** For `useSyncExternalStore`: this tab's changes, and another tab's. */
export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key === THEME_KEY || e.key === null) {
      applyTheme(getTheme());
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/**
 * The script that runs in `<head>`, before the body is parsed. Plain ES5 and self-contained: it is
 * inlined as text, so it cannot import anything. It does what `applyTheme` does for a stored
 * override, and nothing for "system", which is the browser's own default. The attribute is set at
 * once (that is what must precede the first paint); the address-bar tags may not exist yet when the
 * script runs, so they are set again when the document has been parsed.
 */
export const themeScript = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_KEY)});if(t!=="light"&&t!=="dark")return;var c=${JSON.stringify(THEME_COLOURS)};document.documentElement.setAttribute("data-theme",t);var f=function(){var m=document.querySelectorAll('meta[name="theme-color"]');for(var i=0;i<m.length;i++){m[i].setAttribute("media","all");m[i].setAttribute("content",c[t])}};f();document.addEventListener("DOMContentLoaded",f)}catch(e){}})();`;
