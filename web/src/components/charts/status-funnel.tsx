"use client";

import { useLocale } from "next-intl";

import { cn } from "@/lib/cn";

export interface FunnelStage {
  key: string;
  label: string;
  value: number;
}

/**
 * Applied -> shortlisted -> hired, as proportionally-widthed segments.
 *
 * The first stage is always the total, so each later segment's width
 * (`value / stages[0].value`) is a true "how much survived" -- an identity,
 * the same class of arithmetic `CoverageBar`'s `required - shortfall` already
 * runs, never a derived analytic figure of its own.
 */
export function StatusFunnel({
  stages,
  onSelectStage,
  className,
}: {
  stages: FunnelStage[];
  onSelectStage?: (key: string) => void;
  className?: string;
}) {
  const locale = useLocale();
  const fmt = (n: number) => new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(n);
  const total = stages[0]?.value ?? 0;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {stages.map((stage) => {
        const pct = total > 0 ? Math.max(0, Math.min(100, Math.round((stage.value / total) * 100))) : 0;
        const body = (
          <>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium">{stage.label}</span>
              <span className="tabular-nums text-muted">{fmt(stage.value)}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-surface-muted">
              <div className="h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
            </div>
          </>
        );

        if (!onSelectStage) {
          return <div key={stage.key}>{body}</div>;
        }

        return (
          <button
            key={stage.key}
            type="button"
            onClick={() => onSelectStage(stage.key)}
            className="min-h-11 w-full rounded-md text-left"
          >
            {body}
          </button>
        );
      })}
    </div>
  );
}
