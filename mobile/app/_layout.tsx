import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { getLocales } from "expo-localization";
import { Stack } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";

import { resolveLocale } from "../src/core/locale";
import { Intl } from "../src/i18n";
import { api, setLocale, tokens, useLocale, useUpgradeRequired } from "../src/runtime";
import { UpdateRequired } from "../src/screens/UpdateRequired";
import { useColours } from "../src/theme";

/**
 * The root: providers, then start-up, then the gate.
 *
 * **Start-up reads the session before anything renders.** The API client asks for the token on
 * every request, and it is read from the Keychain once, here, into memory (`tokens.load`). A screen
 * that rendered first would make its first request signed out.
 *
 * **The update gate is above the router.** When the API answers 426 to any request, the whole app
 * is replaced by the update screen: nothing underneath it can do anything useful with a server that
 * has said this build is too old (ADR-072).
 */
const queryClient = new QueryClient({
  defaultOptions: {
    // A phone on mobile data: do not hammer a failing request, and do not refetch on every focus.
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
});

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const locale = useLocale();
  const upgrade = useUpgradeRequired();
  const colours = useColours();

  useEffect(() => {
    setLocale(resolveLocale(getLocales().map((l) => l.languageTag)));
    void tokens.load().finally(() => setReady(true));
    // When the session ends (a refresh was refused, or the person signed out), nothing cached
    // about them may be shown to whoever signs in next: the web's `qc.clear()` on sign-out.
    return tokens.subscribe((signedIn) => {
      if (!signedIn) queryClient.clear();
    });
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
      <QueryClientProvider client={queryClient}>
        {upgrade ? (
          <UpdateRequired minVersion={upgrade.minVersion} />
        ) : (
          <Stack screenOptions={{ headerShown: false }} />
        )}
      </QueryClientProvider>
    </Intl>
  );
}

// Kept so the `api` singleton is constructed (and its middleware registered) before first render.
void api;
