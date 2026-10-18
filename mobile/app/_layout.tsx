import { QueryClient, focusManager } from "@tanstack/react-query";
import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { getLocales } from "expo-localization";
import { Stack } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, AppState, View } from "react-native";

import { APP_VERSION, CONFIG_PROBLEMS } from "../src/config";
import { CACHE_STORAGE_KEY, MAX_AGE_MS, dehydrateOptions } from "../src/core/persist";
import { installPluralRules } from "../src/core/plural-polyfill";
import { createSignOutWatch, forgetEverything } from "../src/core/sign-out-watch";
import { Intl } from "../src/i18n";
import {
  api,
  forgetPersistedCache,
  restoreCourseBudget,
  restoreLocale,
  restoreThemePreference,
  tokens,
  useLocale,
  useUpgradeRequired,
} from "../src/runtime";
import { Misconfigured } from "../src/screens/Misconfigured";
import { UpdateRequired } from "../src/screens/UpdateRequired";
import { storage } from "../src/storage";
import { useColours } from "../src/theme";

/**
 * The root: providers, then start-up, then the gate.
 *
 * **Start-up reads the session and the language before anything renders.** The API client asks for
 * the token on every request, and it is read from the Keychain once, here, into memory
 * (`tokens.load`); the language is what the person chose last time (`restoreLocale`). A screen that
 * rendered first would make its first request signed out and in the wrong language.
 *
 * **What is remembered is public data only** (`core/persist.ts`: an allow-list of query keys, a day
 * at most). When the session ends, the in-memory cache and the stored one are both cleared.
 *
 * **A release build with no HTTPS origin does not start** (`core/release.ts`, ADR-077): it shows
 * `Misconfigured` instead of the router, so it can never quietly call a localhost that is not there.
 *
 * **The update gate is above the router.** When the API answers 426 to any request, the whole app
 * is replaced by the update screen: nothing underneath it can do anything useful with a server that
 * has said this build is too old (ADR-072).
 */
const queryClient = new QueryClient({
  defaultOptions: {
    // A phone on mobile data: do not hammer a failing request, and do not refetch on every focus.
    // `gcTime` matches the persisted age: an entry restored from disk must not be collected at once.
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000, gcTime: MAX_AGE_MS },
  },
});

const persister = createAsyncStoragePersister({ storage, key: CACHE_STORAGE_KEY });

// Before the first message is formatted: Hindi's plural rule is not one every engine has.
installPluralRules();

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const locale = useLocale();
  const upgrade = useUpgradeRequired();
  const colours = useColours();

  useEffect(() => {
    // The person sees a plain screen; whoever has the device sees why.
    if (CONFIG_PROBLEMS.length > 0) console.error("release build misconfigured:", CONFIG_PROBLEMS.join(", "));
    // TanStack Query learns "the app came to the front" from the browser; a phone says it through
    // AppState. Without this nothing refetches on return, and the unread count would be stale.
    const sub = AppState.addEventListener("change", (state) => focusManager.setFocused(state === "active"));
    void Promise.all([
      restoreLocale(getLocales().map((l) => l.languageTag)),
      restoreCourseBudget(),
      restoreThemePreference(),
      tokens.load(),
    ]).finally(
      () => setReady(true),
    );
    // When a session that was there ends (a refresh was refused, or the person signed out), nothing
    // cached may be shown to whoever uses the phone next: the web's `qc.clear()` on sign-out. Only
    // the *transition* counts: the first load of a signed-out phone is not a sign-out, and wiping
    // then emptied the offline cache on every launch.
    const unsubscribe = tokens.subscribe(
      createSignOutWatch(() => forgetEverything(queryClient, forgetPersistedCache)),
    );
    return () => {
      sub.remove();
      unsubscribe();
    };
  }, []);

  if (!ready) {
    return (
      <View style={{ flex: 1, justifyContent: "center", backgroundColor: colours.background }}>
        <ActivityIndicator color={colours.brand} accessibilityLabel="Loading" />
      </View>
    );
  }

  return (
    <Intl locale={locale}>
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{ persister, maxAge: MAX_AGE_MS, buster: APP_VERSION, dehydrateOptions }}
      >
        {CONFIG_PROBLEMS.length > 0 ? (
          <Misconfigured />
        ) : upgrade ? (
          <UpdateRequired minVersion={upgrade.minVersion} />
        ) : (
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colours.surface },
              headerTintColor: colours.brand,
              headerTitleStyle: { color: colours.foreground },
              contentStyle: { backgroundColor: colours.background },
            }}
          >
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="sign-in" options={{ headerShown: false }} />
          </Stack>
        )}
      </PersistQueryClientProvider>
    </Intl>
  );
}

// Kept so the `api` singleton is constructed (and its middleware registered) before first render.
void api;
