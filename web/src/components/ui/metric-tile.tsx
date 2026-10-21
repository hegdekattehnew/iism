import type { ReactNode } from "react";

import { IconTile } from "@/components/ui/icon-tile";
import { StatTile } from "@/components/ui/stat-tile";
import { cn } from "@/lib/cn";

/**
 * One dashboard number with a mark (Sprint 88, BL-19.18): the figure and its label as `StatTile` draws
 * them (the number is rendered from what it is handed, `null` is a dash and never a zero), on a quiet
 * tile with an icon beside it, so a row of figures reads as several things and not one run of digits.
 * The icon is passed in as an element, so this module imports no icon: a dashboard names the icons it
 * wants and pays for those. **Not in the `ui` barrel** (it draws a tile, ADR-089), and `StatTile`
 * itself is untouched: it is on every route's first load and `/profile` has under 1 KB left.
 */
export function MetricTile({
  icon,
  value,
  label,
  secondary,
  className,
}: {
  icon: ReactNode;
  value: number | null;
  label: string;
  secondary?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-3 rounded-lg bg-surface-muted p-3", className)}>
      <IconTile>{icon}</IconTile>
      <StatTile value={value} label={label} secondary={secondary} className="min-w-0" />
    </div>
  );
}
