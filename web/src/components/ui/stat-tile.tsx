import { useLocale } from "next-intl";

import { cn } from "@/lib/cn";

/** One number, on a dashboard. Renders fields it is handed and computes
 *  nothing -- the same rule `MatchViz`'s charts follow, for the same reason:
 *  the moment a tile derives its own number it can disagree with the value
 *  the caller actually fetched.
 *
 *  `value === null` renders a placeholder dash rather than "0", the same
 *  distinction `LiveCount` draws between "still loading" and "genuinely
 *  zero" -- a dashboard that cannot tell those apart reports a false zero to
 *  someone whose data just has not arrived yet.
 */
export function StatTile({
  value,
  label,
  secondary,
  className,
}: {
  value: number | null;
  label: string;
  secondary?: string;
  className?: string;
}) {
  const locale = useLocale();
  const fmt = (n: number) => new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(n);

  return (
    <div className={cn("min-w-[7rem]", className)}>
      <div className="text-2xl font-semibold tabular-nums">{value == null ? "—" : fmt(value)}</div>
      <div className="text-xs text-muted">{label}</div>
      {secondary && <div className="mt-0.5 text-xs text-muted">{secondary}</div>}
    </div>
  );
}
