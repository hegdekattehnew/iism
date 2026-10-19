import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * The facts of a listing as a grid of labelled values with an icon on each label (Sprint 85,
 * BL-19.15): pay, experience, place, start, seats. It is a description list (`dl`) because that is
 * what it is, so a screen reader announces each term with its value, and **only `div` groups of
 * `dt` and `dd` sit inside it** (a `<p>` there made every homepage figure list invalid HTML once).
 *
 * The icon repeats the label's word, so it is decorative. Server components, for the reason
 * `IconTile` is.
 */
export function Facts({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <dl
      className={cn(
        "grid gap-4 rounded-xl border border-border-token bg-surface p-5 text-sm shadow-card",
        className,
      )}
    >
      {children}
    </dl>
  );
}

export function Fact({
  icon,
  label,
  children,
  wide = false,
}: {
  /** An icon from `ui/icons`, drawn small beside the label. */
  icon: ReactNode;
  label: string;
  /** The value. More than one `dd` is allowed: the second is a smaller line under the first. */
  children: ReactNode;
  /** Takes the whole row of a two-column grid (a long value such as a qualification's name). */
  wide?: boolean;
}) {
  return (
    <div className={wide ? "col-span-full" : undefined}>
      <dt className="flex items-center gap-1.5 text-xs text-muted">
        <span aria-hidden="true" className="text-brand [&>svg]:h-4 [&>svg]:w-4">
          {icon}
        </span>
        {label}
      </dt>
      {children}
    </div>
  );
}

/** The value of a fact. Kept apart so a caller writes `<FactValue>` and not the classes. */
export function FactValue({ children, large = false }: { children: ReactNode; large?: boolean }) {
  return <dd className={cn("mt-0.5 font-semibold", large ? "text-lg" : "text-base")}>{children}</dd>;
}
