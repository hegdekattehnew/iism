import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/cn";

const badge = cva(
  "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-semibold",
  {
    variants: {
      tone: {
        neutral: "bg-surface-muted text-muted",
        brand: "bg-accent-soft text-brand",
        // Every tone carries its own dark values: a colour defined for one
        // theme and missing in the other is the failure this design system
        // exists to prevent.
        good: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
        warn: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
        bad: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-300",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone }), className)} {...props} />;
}
