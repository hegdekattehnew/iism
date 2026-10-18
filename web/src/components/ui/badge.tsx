import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/cn";

const badge = cva(
  "inline-flex items-center gap-1.5 rounded-md font-semibold",
  {
    variants: {
      // `sm` is the 12 px floor and what every card carries; `md` is for a status that is the point of
      // the row (an application's state), where 12 px beside 15 px text reads as an afterthought.
      size: {
        sm: "px-2 py-0.5 text-2xs",
        md: "px-2.5 py-1 text-xs",
      },
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
        info: "bg-info-surface text-info-text",
      },
    },
    defaultVariants: { tone: "neutral", size: "sm" },
  },
);

export function Badge({
  className,
  tone,
  size,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone, size }), className)} {...props} />;
}
