import { cn } from "@/lib/cn";

/** A loading placeholder shaped like the thing it is replacing.
 *
 * Replaces the bare "…" the app used before: a shape that matches the eventual
 * content stops the page reflowing when data lands, which on a slow connection
 * is most of the perceived jank.
 *
 * `data-loading` is what `globals.css` reads to keep the footer out of sight until nothing on the
 * page is still a placeholder. A footer is the last thing on the page, so when it is on screen
 * beside a half-loaded list, the list landing pushes it down and the whole screen jumps. Any
 * loading placeholder that is not a `Skeleton` must carry the same attribute.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-surface-muted", className)}
      aria-hidden
      data-loading
    />
  );
}

/** The placeholder for a list of cards that has not arrived: as many cards as fit on a phone screen,
 * so the footer, and whatever else sits below the list, is already off-screen and does not move
 * when the real list lands (it is hidden anyway while this is up: see `data-loading`). */
export function ListSkeleton({ rows = 6, className }: { rows?: number; className?: string }) {
  return (
    <ul className={cn("mt-6 grid grid-cols-1 gap-3 lg:grid-cols-2", className)} aria-hidden>
      {Array.from({ length: rows }, (_, i) => (
        <li key={i}>
          <Skeleton className="h-36 w-full rounded-xl" />
        </li>
      ))}
    </ul>
  );
}
