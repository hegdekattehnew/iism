import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/cn";

/**
 * A short message about what just happened, or did not.
 *
 * It exists because the same eleven-class string --
 * `border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 …` --
 * was copied into `CreateOrgForm`, `InterestPanel`, `TeamPanel`, `InvitePanel`
 * and a dozen more. Each copy re-derived its own light/dark pair by hand,
 * which is how one eventually gets missed and renders invisible in one theme.
 *
 * `role="alert"` is the default because that is what nearly every call site
 * wanted and several forgot: a message that appears after a failed submit and
 * is never announced is a message a screen-reader user does not get. Pass
 * `role={undefined}` for a message that is present on first paint -- an alert
 * live region that is already populated announces nothing anyway, and claiming
 * otherwise is noise in the accessibility tree.
 */

const alert = cva("rounded-lg border px-3 py-2 text-sm", {
  variants: {
    tone: {
 danger:"border-danger-border bg-danger-surface text-danger-text",
 warning:"border-warning-border bg-warning-surface text-warning-text",
 success:"border-success-border bg-success-surface text-success-text",
      info: "border-info-border bg-info-surface text-info-text",
    },
  },
  defaultVariants: { tone: "danger" },
});

export function Alert({
  className,
  tone,
  role = "alert",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alert>) {
  return <div role={role} className={cn(alert({ tone }), className)} {...props} />;
}
