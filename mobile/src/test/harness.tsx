import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render } from "@testing-library/react-native";
import type { ReactElement } from "react";

import type { Locale } from "../core/locale";
import { Intl } from "../i18n";

/**
 * Render a screen the way the app does: the real catalogues (the web's, plus the phone's own), a
 * fresh query client with no retries, and nothing mocked about the words. A screen that uses a
 * message key the catalogue lacks renders the key and fails the test that looks for the text.
 *
 * The seam to mock is `../runtime` (the API, the session, the language): see each test.
 */
export async function renderScreen(ui: ReactElement, locale: Locale = "en") {
  // `gcTime: Infinity` because the default five-minute garbage-collection timer keeps Jest's event
  // loop alive after the last test.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  return render(
    <Intl locale={locale}>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </Intl>,
  );
}

/** Let every pending update (a deferred search term, a query that has just answered) land inside `act`. */
export async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}
