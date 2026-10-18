"use client";

import { useState, type ComponentType, type ReactNode } from "react";

/**
 * The footer's appearance control, **closed until it is wanted** (Sprint 78, BL-19.8, ADR-087).
 *
 * Every route's first load includes the footer, and `/profile` is within a few kilobytes of the
 * ceiling (CLAUDE.md, "The header's import graph"), so the switch itself (three buttons, three icons
 * and the theme module) is a separate chunk fetched the first time the disclosure is opened, the way
 * the back office's reference panels are (ADR-083). What stays in the first load is this wrapper, and
 * **the summary arrives as `children` from the server footer**, so its markup and class names are not
 * client JavaScript at all. A plain dynamic `import()` is used rather than `next/dynamic`, whose
 * loader costs more than the thing it loads here. The chosen theme itself is applied by the script in
 * `<head>`, so nothing about *showing* the right theme waits for this chunk.
 */
export function ThemeDisclosure({ children }: { children: ReactNode }) {
  const [Switcher, setSwitcher] = useState<ComponentType | null>(null);

  return (
    <details
      className="group"
      onToggle={(e) => {
        if (e.currentTarget.open && !Switcher) {
          void import("./ThemeSwitcher").then((m) => setSwitcher(() => m.ThemeSwitcher));
        }
      }}
    >
      {children}
      {/* Same height before and after the chunk arrives, so opening it moves nothing below (ADR-065). */}
      <div className="min-h-11 pb-2">{Switcher ? <Switcher /> : null}</div>
    </details>
  );
}
