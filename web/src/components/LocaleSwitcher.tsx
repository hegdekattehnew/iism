"use client";

import { useLocale, useTranslations } from "next-intl";
import { useTransition } from "react";

import { usePathname, useRouter } from "@/i18n/navigation";
import { LOCALES, localeDefinition } from "@/i18n/locales";

/**
 * Choose a language.
 *
 * **A `<select>`, not a row of tabs.** Two tabs fitted; four will not, and
 * eight would wrap into the header on a 360px screen — which is the device
 * this product targets. A native select also costs nothing in accessibility:
 * it is keyboard-operable, announces itself as a menu with the current value,
 * and on a phone opens the platform's own picker.
 *
 * Every option comes from `LOCALES`, so a language added there appears here
 * with no edit to this file.
 */
export function LocaleSwitcher() {
  const t = useTranslations("nav");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [pending, startTransition] = useTransition();

  return (
    <label className="inline-flex items-center gap-2">
      {/* Visible to a screen reader, not to a sighted user: the globe and the
          language name already say what this is. */}
      <span className="sr-only">{t("language")}</span>
      <select
        value={locale}
        disabled={pending}
        onChange={(e) =>
          startTransition(() =>
            // `replace`, so switching language does not fill the back stack
            // with the same page in two languages.
            router.replace(pathname, { locale: e.target.value }),
          )
        }
        className="rounded-lg border border-input-border bg-surface px-2.5 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        {LOCALES.map((l) => (
          <option key={l.code} value={l.code} lang={l.code}>
            {l.nativeName}
          </option>
        ))}
      </select>
    </label>
  );
}

/** The current language's own name — for a footer, where a control would be noise. */
export function CurrentLocaleName() {
  return <>{localeDefinition(useLocale()).nativeName}</>;
}
