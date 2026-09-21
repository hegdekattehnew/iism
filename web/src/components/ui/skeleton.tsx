import { cn } from "@/lib/cn";

/** A loading placeholder shaped like the thing it is replacing.
 *
 * Replaces the bare "…" the app used before: a shape that matches the eventual
 * content stops the page reflowing when data lands, which on a slow connection
 * is most of the perceived jank.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-surface-muted", className)}
      aria-hidden
    />
  );
}
