"use client";

import { useLocale } from "next-intl";

import { cn } from "@/lib/cn";

const TONE_CLASS: Record<"brand" | "warning" | "danger", string> = {
  brand: "bg-brand",
  warning: "bg-warning-solid",
  danger: "bg-danger-solid",
};

export interface RankedBarItem {
  key: string;
  label: string;
  value: number;
  /** Denominator for the bar's width. Defaults to the largest value among `items`. */
  max?: number;
  /** Pre-formatted by the caller -- this component computes nothing. */
  secondary?: string;
  /** Shown in place of the number, for a value the server chose not to send ("fewer than 5"). */
  valueLabel?: string;
  tone?: "brand" | "warning" | "danger";
}

/**
 * A horizontal ranked bar list -- the one new "chart" shape most of this
 * sprint's dashboards need. Every number here is a field of `items`; the only
 * arithmetic is `value / max`, the same layout-only computation `Progress`'s
 * width-from-percent already performs, never a value that could disagree with
 * what the caller fetched.
 *
 * `onSelect` turns each row into a real `<button aria-expanded>` for a caller
 * that wants a drilldown; omitted, rows render as plain read-only text -- the
 * shape `market_scarce_skills` uses, where there is nothing to drill into.
 */
export function RankedBarList({
  items,
  onSelect,
  selectedKey,
  emptyLabel,
  className,
}: {
  items: RankedBarItem[];
  onSelect?: (key: string) => void;
  selectedKey?: string | null;
  emptyLabel: string;
  className?: string;
}) {
  const locale = useLocale();
  const fmt = (n: number) => new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(n);

  if (items.length === 0) {
    return <p className={cn("text-sm text-muted", className)}>{emptyLabel}</p>;
  }

  const max = Math.max(...items.map((item) => item.max ?? item.value), 1);

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {items.map((item) => {
        const pct = Math.max(0, Math.min(100, Math.round((item.value / max) * 100)));
        const body = (
          <>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="truncate font-medium">{item.label}</span>
              <span className="shrink-0 tabular-nums text-muted">
                {item.valueLabel ?? fmt(item.value)}
              </span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-surface-muted">
              <div
                className={cn("h-full rounded-full", TONE_CLASS[item.tone ?? "brand"])}
                style={{ width: `${pct}%` }}
              />
            </div>
            {item.secondary && <p className="mt-0.5 text-xs text-muted">{item.secondary}</p>}
          </>
        );

        if (!onSelect) {
          return (
            <div key={item.key} className="w-full">
              {body}
            </div>
          );
        }

        return (
          <button
            key={item.key}
            type="button"
            aria-expanded={selectedKey === item.key}
            aria-controls={`ranked-bar-panel-${item.key}`}
            onClick={() => onSelect(item.key)}
            className="min-h-11 w-full rounded-md text-left"
          >
            {body}
          </button>
        );
      })}
    </div>
  );
}
