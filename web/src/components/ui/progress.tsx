"use client";

import * as ProgressPrimitive from "@radix-ui/react-progress";
import * as React from "react";

import { cn } from "@/lib/cn";

/** A determinate progress bar.
 *
 * Radix rather than a bare div because it carries the ARIA role, the value and
 * the max, so a screen reader announces "62 percent" instead of nothing.
 */
export function Progress({
  value,
  className,
  indicatorClassName,
  label,
}: {
  value: number;
  className?: string;
  indicatorClassName?: string;
  /** Announced to assistive technology; the visual label is separate. */
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <ProgressPrimitive.Root
      value={clamped}
      aria-label={label}
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-surface-muted",
        className,
      )}
    >
      <ProgressPrimitive.Indicator
        className={cn("h-full rounded-full bg-brand transition-all", indicatorClassName)}
        style={{ width: `${clamped}%` }}
      />
    </ProgressPrimitive.Root>
  );
}
