/**
 * Light, dark, or follow the phone (Sprint 78, BL-19.8, ADR-087).
 *
 * The phone has always followed the system's appearance. A person can now **choose**, and the choice
 * is remembered on the device and nowhere else (never the profile: a taste of one screen is not a
 * fact about a person, ADR-055). It is **forgotten when the session ends**, like the course budget
 * (ADR-078), so a shared phone does not stay in the last person's setting. "System" is the absence of
 * a choice and the default, so a person who never touches it gets what they always got.
 *
 * The store takes its storage as an argument, or later through `attach`, which is what makes it
 * testable in Node and lets `theme/` read it without importing the runtime (every screen test
 * hand-mocks the runtime, and a theme hook that needed it would break them all).
 *
 * No React Native import: this file is tested in Node.
 */

export const THEME_PREFERENCES = ["system", "light", "dark"] as const;
export type ThemePreference = (typeof THEME_PREFERENCES)[number];

export const THEME_STORAGE_KEY = "iism.theme";

/** A stored value is a choice only if it is light or dark; anything else, or nothing, is the phone's own. */
export function parsePreference(raw: unknown): ThemePreference {
  return raw === "light" || raw === "dark" ? raw : "system";
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
  /** Reads what was kept at the last launch; an unreadable or unknown value is "system". */
  restore: () => Promise<void>;
  /** The session ended: back to the phone's own setting, in memory and on disk. */
  clear: () => Promise<void>;
  subscribe: (listener: () => void) => () => void;
};

export function createThemeStore(initial?: KeyValueStore): ThemeStore {
  let storage = initial;
  let current: ThemePreference = "system";
  const listeners = new Set<() => void>();
  const announce = () => listeners.forEach((l) => l());

  return {
    get: () => current,
    set(value) {
      current = parsePreference(value);
      announce();
      // Not remembered if storage refuses: the change still applies for this visit.
      const write = current === "system" ? storage?.removeItem(THEME_STORAGE_KEY) : storage?.setItem(THEME_STORAGE_KEY, current);
      void write?.catch(() => undefined);
    },
    attach(next) {
      storage = next;
    },
    async restore() {
      try {
        current = parsePreference(await storage?.getItem(THEME_STORAGE_KEY));
      } catch {
        current = "system";
      }
      announce();
    },
    async clear() {
      current = "system";
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
