import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/cn";

const badge = cva(
  "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-2xs font-semibold",
  {
    variants: {
      tone: {
        neutral: "bg-surface-muted text-muted",
        brand: "bg-accent-soft text-brand",
        // Each tone is one token pair that already carries both themes, so
        // there is no `dark:` half here to forget. This component modelled the
        // idea first; Sprint 26 moved the values into `globals.css` so the
        // other 300-odd sites could share them.
        good: "bg-success-surface text-success-text",
        warn: "bg-warning-surface text-warning-text",
        bad: "bg-danger-surface text-danger-text",
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
