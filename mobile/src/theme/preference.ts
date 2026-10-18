import { useSyncExternalStore } from "react";
import { Appearance } from "react-native";

import { createThemeStore, type ThemePreference } from "../core/theme-preference";

/**
 * The person's light / dark / follow-the-phone choice, for the whole run of the app (Sprint 78,
 * BL-19.8). One store, made **without** storage: the runtime attaches the phone's storage at
 * start-up (`runtime.ts`), so `useColours` can read the choice without importing the runtime, which
 * every screen test replaces by hand.
 */
export const themePreference = createThemeStore();

export const useThemePreference = (): ThemePreference =>
  useSyncExternalStore(themePreference.subscribe, themePreference.get, themePreference.get);

/**
 * Tell the system too, where the platform lets an app, so what the system draws for us (the status
 * bar, a keyboard, an alert) matches the screen. `useColours` does not depend on this: the browser
 * build has no `setColorScheme`, and the screens follow the store either way.
 */
themePreference.subscribe(() => {
  const choice = themePreference.get();
  try {
    Appearance.setColorScheme?.(choice === "system" ? "unspecified" : choice);
  } catch {
    // An older runtime without the call: the screens still follow the store.
  }
});
