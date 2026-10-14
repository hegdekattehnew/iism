import { useSyncExternalStore } from "react";

import { secureBackend } from "./auth/secure-backend";
import { createApi } from "./core/api";
import { DEFAULT_LOCALE, type Locale } from "./core/locale";
import { createTokenStore } from "./core/token-store";
import { API_BASE_URL, APP_VERSION, PLATFORM } from "./config";

/**
 * The few things that live for the whole run of the app: the session, the language, and whether the
 * server has said this build is too old. Module-level singletons with a subscription, read in
 * React through `useSyncExternalStore` (the same primitive the web's `useIsSignedIn` uses).
 */

export const tokens = createTokenStore(secureBackend);

let locale: Locale = DEFAULT_LOCALE;
const localeListeners = new Set<() => void>();
export const setLocale = (next: Locale) => {
  locale = next;
  localeListeners.forEach((l) => l());
};
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
