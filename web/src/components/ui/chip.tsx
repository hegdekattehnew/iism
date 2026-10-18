import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { ChevronDownIcon } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

/**
 * Filters as a row of chips (Sprint 84, BL-19.15; the Product Owner's choice in BL-19.2).
 *
 * The lists used to stack a search box and three or four selects, which pushed the first result about
 * 480 px down an 812 px screen. A row of chips that scrolls sideways holds the same controls in about
 * 44 px, and each chip is **a native `<select>`**: a phone opens its own picker (a bottom sheet on both
 * Android and iOS) with no code from us, it is keyboard and screen-reader complete, and it adds no
 * dialog to the first load (Radix's is ~33 KB). A chip that has a value is drawn filled, so what is
 * narrowing the list can be seen without opening anything; the label is the select's accessible name,
 * and the selected option is what it shows.
 *
 * Every chip is 44 px tall (the product's floor for a target).
 */

export function ChipRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      role="group"
      aria-label={label}
      // Scrolls sideways inside the page's gutter instead of wrapping into more rows; the negative
      // margin lets a chip slide to the screen edge, the padding puts the first one back on the gutter.
      className="-mx-5 flex gap-2 overflow-x-auto px-5 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0"
    >
      {children}
    </div>
  );
}

const chip =
  "inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium transition-colors focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand";

export function ChipSelect({
  label,
  active,
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; active: boolean }) {
  return (
    <span
      className={cn(
        "relative",
        chip,
        active
          ? "border-brand bg-accent-soft text-brand"
          : "border-border-token bg-surface text-foreground hover:border-brand",
        className,
      )}
    >
      <select
        aria-label={label}
        {...props}
        // The select fills the chip so the whole chip is the target; its own arrow is hidden and ours drawn.
        className="min-h-11 cursor-pointer appearance-none bg-transparent py-0 pl-0 pr-6 text-sm font-medium text-inherit focus:outline-none"
      >
        {children}
      </select>
      <ChevronDownIcon aria-hidden="true" className="pointer-events-none absolute right-3 h-4 w-4" />
    </span>
  );
}

export function ChipButton({
  active = false,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        chip,
        active ? "border-brand bg-accent-soft text-brand" : "border-border-token bg-surface hover:border-brand",
        className,
      )}
      {...props}
    />
  );
}
