/**
 * Light, dark, or follow the phone (Sprint 78, BL-19.8, ADR-087).
 *
 * The phone used to follow the system's appearance; **since Sprint 92 it is light by default**, like
 * the website (a person whose phone is in dark mode had never seen the light screens). A person can
 * **choose** dark or "same as the phone", and the choice is remembered on the device and nowhere else (never the profile: a taste of one screen is not a
 * fact about a person, ADR-055). It is **forgotten when the session ends**, like the course budget
 * (ADR-078), so a shared phone does not stay in the last person's setting. Light is the absence of a
 * choice and the default.
 *
 * The store takes its storage as an argument, or later through `attach`, which is what makes it
 * testable in Node and lets `theme/` read it without importing the runtime (every screen test
 * hand-mocks the runtime, and a theme hook that needed it would break them all).
 *
 * No React Native import: this file is tested in Node.
 */

export const THEME_PREFERENCES = ["light", "dark", "system"] as const;
export type ThemePreference = (typeof THEME_PREFERENCES)[number];

export const THEME_STORAGE_KEY = "iism.theme";

/** A stored value is a choice only if it is dark or system; anything else, or nothing, is light. */
export function parsePreference(raw: unknown): ThemePreference {
  return raw === "dark" || raw === "system" ? raw : "light";
}

type KeyValueStore = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
};

export type ThemeStore = {
  get: () => ThemePreference;
  set: (value: ThemePreference) => void;
  /** Gives a store made without storage the one it should keep to (the runtime does, at start-up). */
  attach: (storage: KeyValueStore) => void;
  /** Reads what was kept at the last launch; an unreadable or unknown value is light. */
  restore: () => Promise<void>;
  /** The session ended: back to the default, light, in memory and on disk. */
  clear: () => Promise<void>;
  subscribe: (listener: () => void) => () => void;
};

export function createThemeStore(initial?: KeyValueStore): ThemeStore {
  let storage = initial;
  let current: ThemePreference = "light";
  const listeners = new Set<() => void>();
  const announce = () => listeners.forEach((l) => l());

  return {
    get: () => current,
    set(value) {
      current = parsePreference(value);
      announce();
      // Not remembered if storage refuses: the change still applies for this visit.
      const write = current === "light" ? storage?.removeItem(THEME_STORAGE_KEY) : storage?.setItem(THEME_STORAGE_KEY, current);
      void write?.catch(() => undefined);
    },
    attach(next) {
      storage = next;
    },
    async restore() {
      try {
        current = parsePreference(await storage?.getItem(THEME_STORAGE_KEY));
      } catch {
        current = "light";
      }
      announce();
    },
    async clear() {
      current = "light";
      announce();
      try {
        await storage?.removeItem(THEME_STORAGE_KEY);
      } catch {
        // A store that cannot be written has nothing the next person could read.
      }
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
