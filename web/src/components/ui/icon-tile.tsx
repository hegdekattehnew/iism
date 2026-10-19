import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * An icon on a tinted square (Sprint 85, BL-19.15): the mark a tile, a section or a list row leads
 * with, so a page has something to scan by besides its words. The child is an icon from
 * `ui/icons`; the tint is the brand's soft surface unless the tile says a meaning with a `tone`.
 *
 * **Decorative.** The words beside it say the same thing, so it is hidden from assistive
 * technology; a tile that is the only thing on a control needs a name on the control, not here.
 * A server component on purpose: nothing about it needs the browser, so a page that draws twenty
 * of them ships no JavaScript for them.
 */
const TONES = {
  brand: "bg-accent-soft text-brand",
  good: "bg-success-surface text-success-text",
  info: "bg-info-surface text-info-text",
  warn: "bg-warning-surface text-warning-text",
  neutral: "bg-surface-muted text-muted",
} as const;

const SIZES = {
  md: "h-10 w-10 [&>svg]:h-5 [&>svg]:w-5",
  sm: "h-8 w-8 [&>svg]:h-4 [&>svg]:w-4",
} as const;

export function IconTile({
  children,
  tone = "brand",
  size = "md",
  className,
}: {
  children: ReactNode;
  tone?: keyof typeof TONES;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg",
        SIZES[size],
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
