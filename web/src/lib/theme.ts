/**
 * Light, dark, or follow the device (Sprint 78, BL-19.8, ADR-087; **light by default since Sprint 92**).
 *
 * Until Sprint 92 the product followed `prefers-color-scheme`, so a person whose computer was in
 * dark mode never saw the light page at all (the owner, asking for a white page with aqua on it,
 * had only ever seen the dark one). **Light is now the default**: a person who never touches the
 * control gets the white page whatever their device says, and dark or "same as the device" is a
 * choice. The choice is held in this browser only (`localStorage`, never the account: it is a taste
 * of one screen, not a fact about the person, and ADR-055 would otherwise make it a column to
 * export and erase). Light is the absence of a stored choice.
 *
 * A choice is the attribute `data-theme="dark" | "system"` on `<html>`; `globals.css` answers
 * "dark" with a second copy of the dark tokens, answers "system" with the media query, and a test
 * holds the two copies equal. The attribute must be there **before the first paint**, or a person who chose dark
 * sees a white page flash on every load, so it is set by a small script in `<head>` that runs
 * before the body is parsed (`themeScript`), built from the same constants as the code below so
 * they cannot drift. The CSP allows inline script (CLAUDE.md, the CSP entry).
 *
 * No React in this file: the switch component reads it through `useSyncExternalStore`.
 */

export const THEME_KEY = "iism-theme";
export const THEMES = ["light", "dark", "system"] as const;
export type Theme = (typeof THEMES)[number];

/** The browser's address bar colour for each theme: the page background of `globals.css`. */
export const THEME_COLOURS = { light: "#f8f9fa", dark: "#111417" } as const;

/** A stored value is a choice only if it is "dark" or "system"; anything else is the default, light. */
export function parseTheme(raw: unknown): Theme {
  return raw === "dark" || raw === "system" ? raw : "light";
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
  if (typeof window === "undefined") return "light";
  try {
    return parseTheme(storage()?.getItem(THEME_KEY) ?? null);
  } catch {
    return "light"; // reading can throw as well as access: blocked site data, a full quota
  }
}

/** The colour a theme draws: "system" is whatever the device is in at this moment. */
function resolved(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme;
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

/** Put a choice on the page: the attribute CSS answers (none for light), and the browser's own chrome. */
export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  if (theme === "light") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    meta.removeAttribute("media");
    meta.setAttribute("content", THEME_COLOURS[resolved(theme)]);
  }
}

/**
 * Remember a choice and apply it. Light forgets the choice, because it is the default.
 */
export function setTheme(theme: Theme): void {
  const store = storage();
  try {
    if (theme === "light") store?.removeItem(THEME_KEY);
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
 * "dark" or "system", and nothing for light, which is the page's own default (so the default needs
 * no script to be right). The attribute is set at once (that is what must precede the first paint);
 * the address-bar tag may not exist yet when the script runs, so it is set again when the document
 * has been parsed.
 */
export const themeScript = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_KEY)});if(t!=="dark"&&t!=="system")return;var c=${JSON.stringify(THEME_COLOURS)};document.documentElement.setAttribute("data-theme",t);var r=t==="system"?(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):t;var f=function(){var m=document.querySelectorAll('meta[name="theme-color"]');for(var i=0;i<m.length;i++){m[i].removeAttribute("media");m[i].setAttribute("content",c[r])}};f();document.addEventListener("DOMContentLoaded",f)}catch(e){}})();`;
