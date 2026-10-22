"use client";

import { useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";

import { MonitorIcon, MoonIcon, SunIcon } from "@/components/ui/icons";
import { getTheme, setTheme, subscribeTheme, type Theme } from "@/lib/theme";

const OPTIONS = [
  { value: "light", key: "themeLight", Icon: SunIcon },
  { value: "dark", key: "themeDark", Icon: MoonIcon },
  { value: "system", key: "themeSystem", Icon: MonitorIcon },
] as const satisfies ReadonlyArray<{ value: Theme; key: string; Icon: typeof SunIcon }>;

/**
 * Light, dark, or the same as the device (Sprint 78, BL-19.8, ADR-087). Three buttons in a group,
 * the chosen one marked with `aria-pressed` (a name and a state, which a colour alone is not), each
 * 44 px. It reads the choice with `useSyncExternalStore`, so another tab's change shows here and the
 * server render (always light, since it cannot read this browser) is corrected on hydration.
 */
export function ThemeSwitcher() {
  const t = useTranslations("footer");
  const theme = useSyncExternalStore(subscribeTheme, getTheme, () => "light" as Theme);

  return (
    <div role="group" aria-label={t("appearance")} className="flex flex-wrap gap-2">
      {OPTIONS.map(({ value, key, Icon }) => {
        const chosen = theme === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={chosen}
            onClick={() => setTheme(value)}
            className={`inline-flex min-h-11 items-center gap-2 rounded-lg border px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              chosen
                ? "border-brand bg-accent-soft text-accent-text"
                : "border-input-border bg-surface text-foreground hover:bg-surface-muted"
            }`}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {t(key)}
          </button>
        );
      })}
    </div>
  );
}
