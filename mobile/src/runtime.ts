import { useSyncExternalStore } from "react";

import { secureBackend } from "./auth/secure-backend";
import { createApi } from "./core/api";
import { createBudgetStore } from "./core/course-budget";
import { DEFAULT_LOCALE, isLocale, resolveLocale, type Locale } from "./core/locale";
import { wipePersistedCache } from "./core/persist";
import { signOut } from "./core/sign-in";
import { createTokenStore } from "./core/token-store";
import { unregisterThisDevice } from "./push";
import { API_BASE_URL, APP_VERSION, PLATFORM } from "./config";
import { LOCALE_KEY, storage } from "./storage";
import { themePreference } from "./theme/preference";

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

/**
 * What the person would pay for a course (ADR-078): remembered on the phone, never on the profile,
 * and **forgotten when the session ends**, so a shared phone does not carry the last person's figure.
 */
export const courseBudget = createBudgetStore(storage);
export const setCourseBudget = courseBudget.set;
export const restoreCourseBudget = courseBudget.restore;
export const useCourseBudget = (): number | null =>
  useSyncExternalStore(courseBudget.subscribe, courseBudget.get, courseBudget.get);

/**
 * Signing out: forget what was kept on disk (the in-memory cache is the query client's). The public
 * cache, and the budget and the appearance choice, which are personal in the only way that matters
 * on a shared phone.
 */
export const forgetPersistedCache = async (): Promise<void> => {
  await Promise.all([wipePersistedCache(storage), courseBudget.clear(), themePreference.clear()]);
};

/**
 * Light, dark or follow the phone (Sprint 78, ADR-087): remembered on the phone, never on the
 * profile, and **forgotten when the session ends** for the reason the budget is. The store lives in
 * `theme/` so the colours can read it; it keeps to the phone's storage from here on.
 */
themePreference.attach(storage);
export const setThemePreference = themePreference.set;
export const restoreThemePreference = themePreference.restore;
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
