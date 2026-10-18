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

/**
 * A tone is also a shape, so it does not depend on colour alone (the design brief's third principle).
 *
 * Drawn here from the same shapes as the icon set (`icons.tsx`: XCircle, AlertTriangle, CheckCircle,
 * Info) and not imported from it: `Alert` is on the first load of nearly every route, and four icon
 * exports plus the icon factory cost `/profile` about 1.3 KB of its few thousand bytes of headroom.
 * `tests/test_icon_shapes.py` holds these paths equal to the set's, so they cannot drift.
 */
const SHAPES = {
  danger: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M9 9l6 6", "M15 9l-6 6"],
  warning: ["M12 3.5l10 17H2z", "M12 10v4.5", "M12 17.5v.01"],
  success: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M8 12.5l3 3 5-6"],
  info: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M12 11v6", "M12 7.5v.01"],
} as const;

export function Alert({
  className,
  tone,
  role = "alert",
  icon = true,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> &
  VariantProps<typeof alert> & {
    /** The tone's icon, drawn in the margin (it is positioned, so the children's own layout is untouched). */
    icon?: boolean;
  }) {
  const shape = SHAPES[tone ?? "danger"];
  return (
    <div role={role} className={cn(alert({ tone }), icon && "relative pl-9", className)} {...props}>
      {icon && (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
          className="absolute left-3 top-3 h-4 w-4"
        >
          {shape.map((d) => (
            <path key={d} d={d} />
          ))}
        </svg>
      )}
      {children}
    </div>
  );
}
