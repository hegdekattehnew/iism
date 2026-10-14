/**
 * Plural rules for the shared message catalogues ("1 job", "5 jobs", and Hindi's own rule that 0 and 1
 * are both "one").
 *
 * The web's messages are ICU, and formatting `{count, plural, ...}` needs `Intl.PluralRules`. Hermes
 * ships a subset of `Intl` that differs by platform and that nothing here can run, so the standard
 * FormatJS polyfill is loaded **when the engine lacks plural rules or lacks Hindi**
 * (`shouldPolyfill`); an engine that has them is left alone. Data for English and Hindi only: the two
 * languages the app offers.
 *
 * Called once, before the first message is formatted (`app/_layout.tsx`).
 */

import { shouldPolyfill } from "@formatjs/intl-pluralrules/should-polyfill.js";

export function installPluralRules(): boolean {
  if (!shouldPolyfill("hi") && !shouldPolyfill("en")) return false;
  // A conditional `require` is how a polyfill is loaded only when it is needed (Metro and Jest both
  // resolve it); a dynamic `import()` would make this asynchronous and fail under Jest.
  /* eslint-disable @typescript-eslint/no-require-imports */
  require("@formatjs/intl-pluralrules/polyfill-force.js");
  require("@formatjs/intl-pluralrules/locale-data/en.js");
  require("@formatjs/intl-pluralrules/locale-data/hi.js");
  /* eslint-enable @typescript-eslint/no-require-imports */
  return true;
}
