import type { ReactNode } from "react";
import { IntlProvider } from "use-intl";

import type { Locale } from "../core/locale";
import appEn from "../messages/app.en.json";
import appHi from "../messages/app.hi.json";
// The web's catalogues, copied by `make sync-mobile-messages`: one set of words, read by both.
import en from "../messages/en.json";
import hi from "../messages/hi.json";

/**
 * `mobile` holds the few strings only a phone needs (it is a namespace of its own, so nothing in
 * the web's catalogue is touched). `tests/test_mobile_foundations.py` holds `app.en.json` and
 * `app.hi.json` to the same keys, as the web's parity test does for its three.
 */
const catalogues = {
  en: { ...en, mobile: appEn },
  hi: { ...hi, mobile: appHi },
} as const;

export function Intl({ locale, children }: { locale: Locale; children: ReactNode }) {
  return (
    <IntlProvider
      locale={locale}
      messages={catalogues[locale]}
      timeZone="Asia/Kolkata"
      onError={(error) => {
        // A missing message must be loud in development and never a crash for a person.
        if (__DEV__) console.warn(error.message);
      }}
    >
      {children}
    </IntlProvider>
  );
}
