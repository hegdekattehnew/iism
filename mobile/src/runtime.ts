import { useSyncExternalStore } from "react";

import { secureBackend } from "./auth/secure-backend";
import { createApi } from "./core/api";
import { DEFAULT_LOCALE, isLocale, resolveLocale, type Locale } from "./core/locale";
import { wipePersistedCache } from "./core/persist";
import { signOut } from "./core/sign-in";
import { createTokenStore } from "./core/token-store";
import { unregisterThisDevice } from "./push";
import { API_BASE_URL, APP_VERSION, PLATFORM } from "./config";
import { LOCALE_KEY, storage } from "./storage";

/**
 * The few things that live for the whole run of the app: the session, the language, and whether the
 * server has said this build is too old. Module-level singletons with a subscription, read in
 * React through `useSyncExternalStore` (the same primitive the web's `useIsSignedIn` uses).
 */

export const tokens = createTokenStore(secureBackend);

let locale: Locale = DEFAULT_LOCALE;
const localeListeners = new Set<() => void>();
const announceLocale = () => localeListeners.forEach((l) => l());

/** The person's choice: shown now and **remembered**, so the next launch is in the same language. */
export const setLocale = (next: Locale) => {
  locale = next;
  announceLocale();
  void storage.setItem(LOCALE_KEY, next).catch(() => undefined);
};

/**
 * At start-up, before the first screen: what they chose last time, else the phone's own language.
 * The device default is **not** written back, so a phone whose language changes is followed until
 * the person chooses.
 */
export async function restoreLocale(deviceLanguages: readonly string[]): Promise<void> {
  let saved: string | null = null;
  try {
    saved = await storage.getItem(LOCALE_KEY);
  } catch {
    // A store that cannot be read is the same as nothing saved.
  }
  locale = isLocale(saved) ? saved : resolveLocale(deviceLanguages);
  announceLocale();
}

/** Signing out: forget the public cache on disk too (the in-memory one is the query client's). */
export const forgetPersistedCache = () => wipePersistedCache(storage);
export const getLocale = () => locale;
export const useLocale = () =>
  useSyncExternalStore(
    (l) => {
      localeListeners.add(l);
      return () => localeListeners.delete(l);
    },
    getLocale,
    getLocale,
  );

type Upgrade = { minVersion: string | null } | null;
let upgrade: Upgrade = null;
const upgradeListeners = new Set<() => void>();
export const useUpgradeRequired = (): Upgrade =>
  useSyncExternalStore(
    (l) => {
      upgradeListeners.add(l);
      return () => upgradeListeners.delete(l);
    },
    () => upgrade,
    () => upgrade,
  );

export const useSignedIn = (): boolean =>
  useSyncExternalStore(
    (l) => tokens.subscribe(l),
    () => tokens.access() !== null,
    () => false,
  );

export const api = createApi({
  baseUrl: API_BASE_URL,
  tokens,
  locale: getLocale,
  appVersion: APP_VERSION,
  platform: PLATFORM,
  onUpgradeRequired: (minVersion) => {
    // A new object each time is fine: it only ever goes from null to set.
    upgrade = { minVersion };
    upgradeListeners.forEach((l) => l());
  },
});

/**
 * Sign out. The phone is taken off the person's push list first, while the session still exists:
 * a notification for the person who just left must not reach whoever holds the phone next.
 */
export const endSession = (): Promise<void> => signOut(api, tokens, () => unregisterThisDevice(api));
